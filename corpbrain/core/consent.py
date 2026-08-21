"""클라우드 동의 저장소 — `~/.corpbrain/config.json` (v0.5 스펙 §4.2).

`--engine cloud`의 선행 조건인 '명시 동의'를 담는, 이번 슬라이스의 유일한 영속 설정 파일을
읽고 쓴다. 코어 모듈이므로 CLI에 의존하지 않으며(스펙 §4.5의 이음새), 설정 파일 경로를
주입받을 수 있어 테스트가 사용자 홈 디렉터리를 건드리지 않는다.

읽기는 예외를 밖으로 내지 않는다 — 파일 없음·손상된 JSON·읽기 권한 없음은 모두 '동의 없음'
으로 수렴한다(보안 상태이므로 판정 불가는 거부 쪽으로 기운다). 반대로 쓰기 실패는 사용자가
'동의가 기록됐다'고 오해하면 안 되므로 `ConsentStoreError`(선행 조건 실패)로 올린다.

쓰기는 원자적이다 — 같은 디렉터리의 임시 파일에 쓰고 `os.fsync` 후 `os.replace`로 교체하므로,
쓰기 도중 중단돼도 기존 파일이 깨진 JSON으로 남지 않는다 (스펙 §4.2 '쓰기 방식').

API 키는 이 파일에 절대 쓰지 않는다 — `ANTHROPIC_API_KEY` 환경변수로만 받는다 (스펙 §4.1).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from corpbrain.core.errors import PreconditionError

__all__ = [
    "CONFIG_DIR_NAME",
    "CONFIG_FILENAME",
    "CONSENT_KEY",
    "CONSENT_PROVIDER",
    "ConsentStoreError",
    "default_config_path",
    "grant_cloud_consent",
    "is_cloud_consent_granted",
    "revoke_cloud_consent",
]

#: 홈 디렉터리 아래 설정 폴더 이름.
CONFIG_DIR_NAME = ".corpbrain"
#: 설정 파일 이름.
CONFIG_FILENAME = "config.json"
#: 동의 상태가 사는 최상위 키 (스펙 §4.2 스키마).
CONSENT_KEY = "cloud_consent"
#: 이번 슬라이스의 유일한 클라우드 provider (복수 provider는 스펙 §2 비목표).
CONSENT_PROVIDER = "anthropic"


class ConsentStoreError(PreconditionError):
    """동의 저장소를 갱신하지 못함 — 폴더 생성·기록 실패 (선행 조건 실패, exit 1).

    `errors.py`의 계층을 그대로 재사용해 `PreconditionError`를 상속한다. 어댑터가 이미
    `PreconditionError`를 비-0 종료로 매핑하고 있으므로 별도 매핑을 추가할 필요가 없다.
    """


def default_config_path() -> Path:
    """기본 설정 파일 경로 `~/.corpbrain/config.json` (스펙 §4.2).

    import 시점이 아니라 호출 시점에 홈을 조회한다 — 테스트·다른 어댑터가 환경을 바꿔도
    그대로 따라간다.
    """
    return Path.home() / CONFIG_DIR_NAME / CONFIG_FILENAME


def is_cloud_consent_granted(*, config_path: Path | None = None) -> bool:
    """cloud 엔진(Anthropic) 동의가 기록돼 있는지 판정한다.

    `cloud_consent.anthropic.granted`가 정확히 `True`일 때만 동의로 본다 — 문자열
    `"true"`나 `1` 같은 값은 동의로 취급하지 않는다(보안 상태를 느슨하게 읽지 않는다).
    파일 없음·손상된 JSON·읽기 권한 없음도 모두 `False`이며 예외를 올리지 않는다 (스펙 §4.2).

    Args:
        config_path: 설정 파일 경로. `None`이면 `default_config_path()`.
    """
    document = _read_document(config_path or default_config_path())
    consent = document.get(CONSENT_KEY)
    if not isinstance(consent, dict):
        return False
    provider = consent.get(CONSENT_PROVIDER)
    if not isinstance(provider, dict):
        return False
    return provider.get("granted") is True


def grant_cloud_consent(*, config_path: Path | None = None) -> None:
    """동의를 기록한다 — 파일이 없으면 만들고, 있으면 `cloud_consent.anthropic`만 갱신한다.

    다른 최상위 키와 `cloud_consent` 아래 다른 provider 키는 그대로 보존한다(후속 설정
    확장을 위한 이음새, 스펙 §4.2). 다만 기존 파일이 JSON으로 읽히지 않으면(손상·비-객체)
    보존할 내용을 알 수 없으므로 새 문서로 덮어쓴다 — 동의 기록이 손상된 파일 때문에
    영구히 막히지 않게 한다.

    Args:
        config_path: 설정 파일 경로. `None`이면 `default_config_path()`.

    Raises:
        ConsentStoreError: 설정 폴더 생성 또는 파일 기록에 실패한 경우.
    """
    path = config_path or default_config_path()
    document = _read_document_for_update(path)
    document[CONSENT_KEY] = _with_provider(
        document,
        {"granted": True, "granted_at": datetime.now(UTC).isoformat()},
    )
    _write_document(path, document)


def revoke_cloud_consent(*, config_path: Path | None = None) -> None:
    """동의를 철회한다 — `cloud_consent.anthropic.granted`를 `False`로 남긴다 (스펙 §4.2).

    키를 제거하는 대신 `granted: false`를 남겨 '한 번도 묻지 않음'과 '명시적으로 철회함'을
    파일만 봐도 구분할 수 있게 한다. `granted_at`은 의미를 잃으므로 함께 지운다. 파일이
    없어도 실패가 아니라 철회된 상태를 기록해 사후 상태를 결정적으로 만든다(멱등).
    다른 키는 grant와 동일하게 보존한다.

    Args:
        config_path: 설정 파일 경로. `None`이면 `default_config_path()`.

    Raises:
        ConsentStoreError: 설정 폴더 생성 또는 파일 기록에 실패한 경우.
    """
    path = config_path or default_config_path()
    document = _read_document_for_update(path)
    document[CONSENT_KEY] = _with_provider(document, {"granted": False})
    _write_document(path, document)


def _with_provider(document: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """기존 `cloud_consent` 블록에서 `anthropic` 항목만 교체한 새 블록을 만든다."""
    existing = document.get(CONSENT_KEY)
    consent = dict(existing) if isinstance(existing, dict) else {}
    consent[CONSENT_PROVIDER] = entry
    return consent


def _read_document(path: Path) -> dict[str, Any]:
    """설정 파일을 dict로 읽는다. 읽을 수 없거나 최상위가 객체가 아니면 빈 dict.

    **조회 전용**이다. 호출자가 '동의 없음'으로 안전하게 진행할 수 있도록 어떤 예외도 밖으로
    내지 않는다(파일 없음·권한 거부·깨진 JSON·UTF-8 디코딩 실패 모두 동일 취급). 조회에서
    빈 dict는 곧 '동의 없음'이라 안전한 방향으로 실패하는 셈이다.

    갱신(grant/revoke) 경로는 이 함수를 쓰지 않는다 — `_read_document_for_update` 참조.
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


def _read_document_for_update(path: Path) -> dict[str, Any]:
    """갱신 직전에 기존 문서를 읽는다 — 보존할 수 없는 상황이면 덮어쓰지 않고 실패한다.

    조회(`_read_document`)와 달리 **'파일이 없다'와 '파일을 읽지 못했다'를 구분**한다.
    둘 다 빈 dict로 뭉개면, 동기화 클라이언트가 잠갔거나 권한이 잠시 막힌 것뿐인
    멀쩡한 설정 파일을 통째로 덮어써 다른 키를 날리게 된다(스펙 §4.2가 요구한 "다른 키는
    보존" 이음새가 바로 그때 깨진다).

    - 파일 없음 → 빈 dict (새로 만든다)
    - 내용이 파싱 불가(깨진 JSON·비-객체·디코딩 실패) → 빈 dict (보존할 내용을 알 수 없으므로
      새 문서로 덮어쓴다 — 손상 파일 때문에 동의 기록이 영구히 막히지 않게 한다)
    - 그 밖의 읽기 실패(권한 거부 등) → `ConsentStoreError` (내용이 멀쩡할 수 있으므로 보호한다)
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError:
        return {}  # 내용을 해석할 수 없다 — 보존할 대상이 없다
    except OSError as exc:
        raise ConsentStoreError(
            f"설정 파일을 읽지 못해 갱신을 중단했습니다: {path} ({exc}) — "
            f"덮어쓰면 기존 설정이 사라질 수 있습니다. 권한·잠금을 확인한 뒤 다시 실행하세요."
        ) from exc
    try:
        document = json.loads(raw)
    except ValueError:  # 깨진 JSON
        return {}
    return document if isinstance(document, dict) else {}


def _write_document(path: Path, document: dict[str, Any]) -> None:
    """설정 문서를 원자적으로 기록한다 (임시 파일 → fsync → `os.replace`, 스펙 §4.2).

    임시 파일은 반드시 대상과 같은 디렉터리에 만든다 — `os.replace`는 동일 볼륨에서만
    원자적으로 동작한다. 실패하면 임시 파일을 지워 잔여물을 남기지 않는다.
    """
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConsentStoreError(
            f"설정 폴더를 만들지 못했습니다: {path.parent} ({exc})"
        ) from exc

    try:
        # mkstemp는 0600으로 파일을 만든다 — 교체 후에도 그 권한이 유지된다.
        handle_fd, tmp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
        )
    except OSError as exc:
        raise ConsentStoreError(
            f"설정 파일 임시본을 만들지 못했습니다: {path} ({exc})"
        ) from exc

    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise ConsentStoreError(f"설정 파일을 기록하지 못했습니다: {path} ({exc})") from exc
