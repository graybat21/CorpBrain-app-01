"""`~/.corpbrain/config.json` 읽기·쓰기 — 여러 섹션이 공유하는 단일 설정 파일 (v0.9 §4.8).

v0.5 는 이 파일을 `cloud_consent` 한 섹션만 쓰는 것으로 만들었고, 쓰기 절차(갱신 직전 재읽기
→ 자기 섹션만 교체 → 임시파일 + fsync + `os.replace`)를 `consent.py` 안에 두었다. v0.9 GUI 가
`gui` 섹션을 같은 파일에 쓰면서 그 절차의 소유자가 둘이 되었으므로, 절차만 이 모듈로 옮기고
두 섹션이 **같은 함수 하나**를 부르게 한다.

복사해 두 벌로 두지 않는 이유는 그 절차가 지키는 성질이 **섹션 사이의 성질**이기 때문이다 —
GUI 서버가 떠 있는 동안 사용자가 다른 터미널에서 동의를 승인·철회하면, 「읽기 → 수정 → 통째로
쓰기」를 하는 쪽이 상대 섹션을 날린다. 동의가 조용히 철회되면 클라우드 스캔이 막히고 원인이
드러나지 않는다. 한쪽만 고쳐지는 순간 그 성질이 한쪽에서만 성립하고, 어긋남은 설정이 사라진
한참 뒤에야 드러난다.

파일 락은 두지 않는다 — POSIX `fcntl` 과 Windows `msvcrt` 분기를 코어에 들이는 대가가 설정
저장 빈도에 비해 과하다. 재읽기와 `rename` 사이의 이론적 레이스는 알려진 한계로 둔다 (v0.9 §4.8).

API 키는 이 파일에 절대 쓰지 않는다 — `ANTHROPIC_API_KEY` 환경변수로만 받는다 (v0.5 §4.1).
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from corpbrain.core.errors import PreconditionError

__all__ = [
    "CONFIG_DIR_NAME",
    "CONFIG_FILENAME",
    "ConfigStoreError",
    "default_config_path",
    "read_document",
    "read_section",
    "update_section",
]

#: 홈 디렉터리 아래 설정 폴더 이름.
CONFIG_DIR_NAME = ".corpbrain"
#: 설정 파일 이름.
CONFIG_FILENAME = "config.json"


class ConfigStoreError(PreconditionError):
    """설정 파일을 갱신하지 못함 — 폴더 생성·기록 실패 (선행 조건 실패, exit 1).

    `errors.py`의 계층을 그대로 재사용해 `PreconditionError`를 상속한다. 어댑터가 이미
    `PreconditionError`를 비-0 종료로 매핑하고 있으므로 별도 매핑을 추가할 필요가 없다.
    """


def default_config_path() -> Path:
    """기본 설정 파일 경로 `~/.corpbrain/config.json` (v0.5 §4.2).

    import 시점이 아니라 호출 시점에 홈을 조회한다 — 테스트·다른 어댑터가 환경을 바꿔도
    그대로 따라간다.
    """
    return Path.home() / CONFIG_DIR_NAME / CONFIG_FILENAME


def read_document(path: Path) -> dict[str, Any]:
    """설정 파일을 dict로 읽는다. 읽을 수 없거나 최상위가 객체가 아니면 빈 dict.

    **조회 전용**이다. 호출자가 '설정 없음'으로 안전하게 진행할 수 있도록 어떤 예외도 밖으로
    내지 않는다(파일 없음·권한 거부·깨진 JSON·UTF-8 디코딩 실패 모두 동일 취급). 동의 조회에서
    빈 dict는 곧 '동의 없음'이라 안전한 방향으로 실패하는 셈이다.

    갱신 경로는 이 함수를 쓰지 않는다 — `_read_document_for_update` 참조.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):  # 파일 없음·권한 거부·디코딩 실패(UnicodeDecodeError)
        return {}
    try:
        document = json.loads(raw)
    except ValueError:  # 깨진 JSON
        return {}
    return document if isinstance(document, dict) else {}


def read_section(path: Path, key: str) -> dict[str, Any]:
    """한 섹션을 dict로 읽는다. 섹션이 없거나 객체가 아니면 빈 dict (조회 전용)."""
    section = read_document(path).get(key)
    return section if isinstance(section, dict) else {}


def update_section(
    path: Path,
    key: str,
    replace: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    error_type: type[ConfigStoreError] = ConfigStoreError,
) -> None:
    """자기 섹션 하나만 교체해 설정 파일을 원자적으로 갱신한다 (v0.9 §4.8).

    절차는 **재읽기 → 자기 섹션만 교체 → 임시파일 후 `rename`** 이다. 다른 최상위 키와 자기
    섹션 밖의 값은 그대로 보존된다. 기존 파일이 JSON으로 읽히지 않으면(손상·비-객체) 보존할
    내용을 알 수 없으므로 새 문서로 덮어쓴다 — 손상 파일 때문에 기록이 영구히 막히지 않게 한다.

    Args:
        path: 설정 파일 경로.
        key: 갱신할 최상위 섹션 키 (`cloud_consent` · `gui`).
        replace: 기존 섹션(없으면 빈 dict)을 받아 새 섹션을 돌려주는 순수 함수.
        error_type: 실패 시 올릴 예외 클래스. 호출부가 이미 자기 도메인 예외를 공표해 둔
            경우(`ConsentStoreError`)를 위해 열어 둔다 — 절차를 공유하면서도 어댑터가 보는
            예외 종류는 종전대로 유지된다.

    Raises:
        error_type: 설정 폴더 생성 또는 파일 기록에 실패한 경우, 그리고 기존 파일을 읽지
            못해(권한 거부 등) 덮어쓰면 내용이 사라질 수 있는 경우.
    """
    document = _read_document_for_update(path, error_type)
    existing = document.get(key)
    document[key] = replace(dict(existing) if isinstance(existing, dict) else {})
    _write_document(path, document, error_type)


def _read_document_for_update(
    path: Path, error_type: type[ConfigStoreError]
) -> dict[str, Any]:
    """갱신 직전에 기존 문서를 읽는다 — 보존할 수 없는 상황이면 덮어쓰지 않고 실패한다.

    조회(`read_document`)와 달리 **'파일이 없다'와 '파일을 읽지 못했다'를 구분**한다.
    둘 다 빈 dict로 뭉개면, 동기화 클라이언트가 잠갔거나 권한이 잠시 막힌 것뿐인
    멀쩡한 설정 파일을 통째로 덮어써 다른 키를 날리게 된다(v0.5 §4.2가 요구한 "다른 키는
    보존" 이음새가 바로 그때 깨진다).

    - 파일 없음 → 빈 dict (새로 만든다)
    - 내용이 파싱 불가(깨진 JSON·비-객체·디코딩 실패) → 빈 dict (보존할 내용을 알 수 없으므로
      새 문서로 덮어쓴다 — 손상 파일 때문에 기록이 영구히 막히지 않게 한다)
    - 그 밖의 읽기 실패(권한 거부 등) → `error_type` (내용이 멀쩡할 수 있으므로 보호한다)
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError:
        return {}  # 내용을 해석할 수 없다 — 보존할 대상이 없다
    except OSError as exc:
        raise error_type(
            f"설정 파일을 읽지 못해 갱신을 중단했습니다: {path} ({exc}) — "
            f"덮어쓰면 기존 설정이 사라질 수 있습니다. 권한·잠금을 확인한 뒤 다시 실행하세요."
        ) from exc
    try:
        document = json.loads(raw)
    except ValueError:  # 깨진 JSON
        return {}
    return document if isinstance(document, dict) else {}


def _write_document(
    path: Path, document: dict[str, Any], error_type: type[ConfigStoreError]
) -> None:
    """설정 문서를 원자적으로 기록한다 (임시 파일 → fsync → `os.replace`, v0.5 §4.2).

    임시 파일은 반드시 대상과 같은 디렉터리에 만든다 — `os.replace`는 동일 볼륨에서만
    원자적으로 동작한다. 실패하면 임시 파일을 지워 잔여물을 남기지 않는다.
    """
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise error_type(f"설정 폴더를 만들지 못했습니다: {path.parent} ({exc})") from exc

    try:
        # mkstemp는 0600으로 파일을 만든다 — 교체 후에도 그 권한이 유지된다.
        handle_fd, tmp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
        )
    except OSError as exc:
        raise error_type(f"설정 파일 임시본을 만들지 못했습니다: {path} ({exc})") from exc

    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:
        # `OSError`만 잡으면 인코딩 실패(`UnicodeEncodeError`는 `ValueError` 계열) 같은
        # 비-OSError가 그대로 빠져나가 ① 임시본이 잔여물로 남고 ② 도메인 예외가 아니라서
        # 어댑터의 exit 1 매핑을 비켜 트레이스백이 그대로 노출된다.
        # 어떤 원인이든 임시본을 지우고 도메인 예외로 감싼다.
        tmp_path.unlink(missing_ok=True)
        raise error_type(f"설정 파일을 기록하지 못했습니다: {path} ({exc})") from exc
