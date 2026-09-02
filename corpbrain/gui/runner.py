"""스캔 자식 프로세스의 진입점 (v0.9 스펙 §4.4).

스캔은 **별도 프로세스**로 돈다. 코어에 협조적 취소 이음새가 없고(`run_scan`은 동기
블로킹이며 `on_event` 콜백의 예외를 삼킨다), `tests/test_core_api_smoke.py`가 그 파라미터
목록을 정확히 일치로 단언해 인자를 더할 수도 없기 때문이다. **중지는 프로세스 종료로**
구현하며, 프로세스 경계가 sqlite 스레드 문제도 함께 막아 준다.

프로토콜:

- **입력**: `ScanConfig`에 해당하는 값을 JSON으로 **stdin**에 받는다. 명령줄 인자로 넘기지
  않는다 — 경로에 공백·비ASCII가 흔하고 프로세스 목록에 노출된다.
- **출력**: stdout에 **JSON 한 줄 = 이벤트 하나**. 마지막에 §4.4.1의 종료 레코드 한 줄.
- **종료 코드**: CLI와 같은 매핑 — 0 정상, 1 선행 조건 실패, 3 자원 게이트 차단.

`corpbrain.core._progress`를 import 하는 것은 **이 모듈뿐**이다. 서버는 JSON dict만
다루므로 `ProgressEvent`를 공개 API로 승격하지 않아도 된다 — 러너는 `corpbrain` 패키지
내부 모듈이라 `_progress`가 허용한 "패키지 내부는 직접 import 한다"에 해당한다.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from corpbrain.core._progress import ProgressEvent
from corpbrain.core.config import ScanConfig
from corpbrain.core.errors import PreconditionError, TokenBudgetExceededError
from corpbrain.core.models import ScanResult
from corpbrain.core.pipeline import run_scan

__all__ = [
    "LASTRUN_FILENAME",
    "RECORD_SCHEMA",
    "build_record",
    "config_from_payload",
    "force_utf8_streams",
    "lastrun_path",
    "main",
    "read_lastrun",
    "run",
    "write_lastrun",
]

#: 종료 레코드의 형식 버전. 값이 다른 `lastrun.json`은 읽지 않고 무시한다 (§4.4.1).
RECORD_SCHEMA = 1

#: `out_dir` 아래 숨김 파일 — 기존 두 저장소와 같은 관용구다 (§4.3.1).
LASTRUN_FILENAME = ".corpbrain_gui_lastrun.json"

#: 종료 코드 — CLI(`corpbrain/cli.py`)와 같은 매핑이다.
EXIT_OK = 0
EXIT_PRECONDITION_FAILED = 1
EXIT_LIMIT_EXCEEDED = 3

#: 페이로드가 채울 수 있는 `ScanConfig` 필드. 모르는 키는 거절한다.
_CONFIG_FIELDS = frozenset(field.name for field in dataclasses.fields(ScanConfig))

#: 절대경로여야 하는 필드 (§4.5).
_PATH_FIELDS = ("folder", "out_dir")


# --- 직렬화 (§4.4.1) -------------------------------------------------------------


def _plain(value: Any) -> Any:
    """`Path`·`StrEnum`·중첩 dataclass를 JSON이 되는 값으로 바꾼다.

    변환 규칙은 스펙 §4.4.1 표 그대로다 — `Path`는 문자열, `Enum`은 멤버의 값, `None`은
    `null`, 중첩 dataclass는 중첩 객체.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {name: _plain(item) for name, item in _fields_of(value)}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    return value


def _fields_of(instance: Any) -> list[tuple[str, Any]]:
    """dataclass 필드 + **총계 프로퍼티**.

    `GraphStats.nodes`·`edges`는 프로퍼티라 `dataclasses.fields()`에 잡히지 않는다. 그냥
    직렬화하면 화면의 총계가 조용히 빈다 (§4.4.1).
    """
    pairs = [
        (field.name, getattr(instance, field.name))
        for field in dataclasses.fields(instance)
    ]
    for extra in ("nodes", "edges"):
        prop = getattr(type(instance), extra, None)
        if isinstance(prop, property):
            pairs.append((extra, getattr(instance, extra)))
    return pairs


def build_record(
    result: ScanResult,
    *,
    workspace_id: str,
    exit_code: int,
    finished_at: str | None = None,
) -> dict[str, Any]:
    """`ScanResult`를 **손실 없이** 직렬화하고 어댑터 정보 넷을 더한다 (§4.4.1)."""
    record = {name: _plain(value) for name, value in _fields_of(result)}
    record.update(
        schema=RECORD_SCHEMA,
        workspace_id=workspace_id,
        exit_code=exit_code,
        finished_at=finished_at or datetime.now(UTC).isoformat(),
    )
    return record


def build_failure_record(
    *,
    out_dir: Path,
    workspace_id: str,
    exit_code: int,
    error: str,
    finished_at: str | None = None,
) -> dict[str, Any]:
    """`run_scan`이 선행 조건 실패로 멈춰 `ScanResult`가 없을 때의 종료 레코드."""
    return {
        "schema": RECORD_SCHEMA,
        "workspace_id": workspace_id,
        "exit_code": exit_code,
        "finished_at": finished_at or datetime.now(UTC).isoformat(),
        "out_dir": str(out_dir),
        "error": error,
    }


# --- lastrun.json (§4.3.1) -------------------------------------------------------


def lastrun_path(out_dir: Path) -> Path:
    return out_dir / LASTRUN_FILENAME


def write_lastrun(out_dir: Path, record: dict[str, Any]) -> None:
    """원자적으로 기록한다. 스캔 종료 직후 한 번만 쓰므로 비용이 없다."""
    target = lastrun_path(out_dir)
    body = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
    except BaseException:
        with suppress(OSError):
            os.unlink(temp_name)
        raise


def read_lastrun(out_dir: Path) -> dict[str, Any] | None:
    """마지막 실행 결과를 읽는다. 없거나 읽을 수 없으면 `None`.

    **`schema`가 다르면 읽지 않고 무시한다.** 표시용 사본이므로 자동 복구도 오류도 필요
    없다 — 다음 스캔이 덮어쓴다. 저장소 스키마 불일치를 오류로 다루는 v0.4·v0.6 방침과
    갈리는 지점이며, **정본이 아니기 때문에** 갈라도 된다 (§4.4.1).
    """
    try:
        document = json.loads(lastrun_path(out_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict) or document.get("schema") != RECORD_SCHEMA:
        return None
    return document


# --- 입력 (§4.4) -----------------------------------------------------------------


def config_from_payload(payload: dict[str, Any]) -> ScanConfig:
    """stdin JSON을 `ScanConfig`로 만든다.

    생략된 필드는 **코어 기본값**을 쓴다 — 서버가 값을 지어내지 않는다 (§4.7.1).

    Raises:
        ValueError: 모르는 키가 있거나, 경로가 절대경로가 아니다.
    """
    unknown = set(payload) - _CONFIG_FIELDS
    if unknown:
        raise ValueError(f"알 수 없는 설정 키: {sorted(unknown)}")

    kwargs = dict(payload)
    for name in _PATH_FIELDS:
        if name not in kwargs:
            raise ValueError(f"{name}은(는) 반드시 지정해야 합니다.")
        path = Path(str(kwargs[name]))
        if not path.is_absolute():
            raise ValueError(f"{name}은(는) 절대경로여야 합니다: {path}")
        kwargs[name] = path
    return ScanConfig(**kwargs)


# --- 진입점 (§4.4) ---------------------------------------------------------------


def run(stdin: TextIO, stdout: TextIO, *, workspace_id: str) -> int:
    """스캔을 한 번 돌리고 이벤트와 종료 레코드를 `stdout`에 쓴다."""

    def emit(payload: dict[str, Any]) -> None:
        stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stdout.flush()

    try:
        config = config_from_payload(json.loads(stdin.read()))
    except (ValueError, json.JSONDecodeError) as exc:
        emit(
            build_failure_record(
                out_dir=Path("."),
                workspace_id=workspace_id,
                exit_code=EXIT_PRECONDITION_FAILED,
                error=str(exc),
            )
        )
        return EXIT_PRECONDITION_FAILED

    def on_event(event: ProgressEvent) -> None:
        emit(event.to_dict())

    try:
        result = run_scan(config, on_event=on_event)
    except TokenBudgetExceededError as exc:
        record = build_failure_record(
            out_dir=config.out_dir,
            workspace_id=workspace_id,
            exit_code=EXIT_LIMIT_EXCEEDED,
            error=str(exc),
        )
        _persist(config.out_dir, record)
        emit(record)
        return EXIT_LIMIT_EXCEEDED
    except PreconditionError as exc:
        record = build_failure_record(
            out_dir=config.out_dir,
            workspace_id=workspace_id,
            exit_code=EXIT_PRECONDITION_FAILED,
            error=str(exc),
        )
        _persist(config.out_dir, record)
        emit(record)
        return EXIT_PRECONDITION_FAILED

    # `limit_exceeded`는 예외가 아니라 결과 필드다 — 놓치기 쉬운 지점이다 (CLI와 같은 매핑).
    exit_code = EXIT_LIMIT_EXCEEDED if result.limit_exceeded else EXIT_OK
    record = build_record(result, workspace_id=workspace_id, exit_code=exit_code)
    _persist(config.out_dir, record)
    emit(record)
    return exit_code


def _persist(out_dir: Path, record: dict[str, Any]) -> None:
    """`lastrun.json` 기록은 **베스트 에포트**다 — 실패해도 스캔 결과를 무효화하지 않는다."""
    with suppress(OSError):
        write_lastrun(out_dir, record)


def force_utf8_streams() -> None:
    """stdin/stdout/stderr를 UTF-8로 맞춘다.

    **이것이 없으면 한글 경로에서 스캔이 통째로 실패한다.** Windows 기본 콘솔 코드페이지는
    cp949라 자식이 한글을 cp949로 내보내는데, 부모는 UTF-8로 읽어 디코딩이 깨진다. 결과를
    받지 못한 부모는 「결과 없이 종료했습니다」라고만 보고하고 진짜 이유는 사라진다.

    `corpbrain/cli.py`의 `_force_utf8_output()`과 같은 조치이며, 그쪽이 콘솔 표시를 위한
    것이라면 이쪽은 **프로세스 사이 프로토콜**을 위한 것이다. 재구성이 불가능한 스트림은
    조용히 건너뛴다.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            continue


def main(argv: list[str] | None = None) -> int:
    """`python -m corpbrain.gui.runner <workspace_id>`."""
    force_utf8_streams()
    args = sys.argv[1:] if argv is None else argv
    workspace_id = args[0] if args else ""
    return run(sys.stdin, sys.stdout, workspace_id=workspace_id)


if __name__ == "__main__":  # pragma: no cover - 프로세스 진입점
    raise SystemExit(main())
