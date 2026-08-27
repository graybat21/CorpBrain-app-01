"""클라우드 동의 저장소 — `~/.corpbrain/config.json`의 `cloud_consent` 섹션 (v0.5 스펙 §4.2).

`--engine cloud`의 선행 조건인 '명시 동의'를 담는 섹션을 읽고 쓴다. 코어 모듈이므로 CLI에
의존하지 않으며(스펙 §4.5의 이음새), 설정 파일 경로를 주입받을 수 있어 테스트가 사용자 홈
디렉터리를 건드리지 않는다.

읽기는 예외를 밖으로 내지 않는다 — 파일 없음·손상된 JSON·읽기 권한 없음은 모두 '동의 없음'
으로 수렴한다(보안 상태이므로 판정 불가는 거부 쪽으로 기운다). 반대로 쓰기 실패는 사용자가
'동의가 기록됐다'고 오해하면 안 되므로 `ConsentStoreError`(선행 조건 실패)로 올린다.

**파일 입출력 절차 자체는 이 모듈이 소유하지 않는다** — `configstore.update_section()`이
「재읽기 → 자기 섹션만 교체 → 임시파일 후 `rename`」을 수행하며, v0.9 GUI의 `gui` 섹션이 같은
함수를 쓴다. 두 섹션이 한 파일을 쓰므로 절차가 두 벌이면 나중에 쓴 쪽이 상대 섹션을 날린다
(v0.9 §4.8).

API 키는 이 파일에 절대 쓰지 않는다 — `ANTHROPIC_API_KEY` 환경변수로만 받는다 (스펙 §4.1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from corpbrain.core.configstore import (
    CONFIG_DIR_NAME,
    CONFIG_FILENAME,
    ConfigStoreError,
    default_config_path,
    read_section,
    update_section,
)

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

#: 동의 상태가 사는 최상위 키 (스펙 §4.2 스키마).
CONSENT_KEY = "cloud_consent"
#: 이번 슬라이스의 유일한 클라우드 provider (복수 provider는 스펙 §2 비목표).
CONSENT_PROVIDER = "anthropic"


class ConsentStoreError(ConfigStoreError):
    """동의 저장소를 갱신하지 못함 — 폴더 생성·기록 실패 (선행 조건 실패, exit 1).

    `configstore.ConfigStoreError`를 상속하고 그것이 다시 `PreconditionError`를 상속한다.
    어댑터가 이미 `PreconditionError`를 비-0 종료로 매핑하고 있으므로 별도 매핑이 필요 없고,
    동의 경로가 올리는 예외 종류는 v0.5 그대로 유지된다 — 공유 헬퍼로 절차를 옮기면서
    호출자가 보는 계약이 바뀌지 않게 한다.
    """


def is_cloud_consent_granted(*, config_path: Path | None = None) -> bool:
    """cloud 엔진(Anthropic) 동의가 기록돼 있는지 판정한다.

    `cloud_consent.anthropic.granted`가 정확히 `True`일 때만 동의로 본다 — 문자열
    `"true"`나 `1` 같은 값은 동의로 취급하지 않는다(보안 상태를 느슨하게 읽지 않는다).
    파일 없음·손상된 JSON·읽기 권한 없음도 모두 `False`이며 예외를 올리지 않는다 (스펙 §4.2).

    Args:
        config_path: 설정 파일 경로. `None`이면 `default_config_path()`.
    """
    consent = read_section(config_path or default_config_path(), CONSENT_KEY)
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
    entry = {"granted": True, "granted_at": datetime.now(UTC).isoformat()}
    _update_provider(config_path, entry)


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
    _update_provider(config_path, {"granted": False})


def _update_provider(config_path: Path | None, entry: dict[str, Any]) -> None:
    """`cloud_consent` 섹션에서 `anthropic` 항목만 교체한다 — 다른 provider는 보존한다."""

    def _replace(section: dict[str, Any]) -> dict[str, Any]:
        section[CONSENT_PROVIDER] = entry
        return section

    update_section(
        config_path or default_config_path(),
        CONSENT_KEY,
        _replace,
        error_type=ConsentStoreError,
    )
