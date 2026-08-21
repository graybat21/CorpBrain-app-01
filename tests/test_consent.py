"""동의 저장소 단위테스트 (v0.5 스펙 §4.2 — 스키마·보존·안전 판정·원자적 쓰기).

모든 테스트는 `tmp_path`로 격리한다 — 실제 홈 디렉터리(`~/.corpbrain/config.json`)를
읽지도 쓰지도 않는다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core.consent import (
    CONFIG_DIR_NAME,
    CONFIG_FILENAME,
    CONSENT_KEY,
    CONSENT_PROVIDER,
    ConsentStoreError,
    default_config_path,
    grant_cloud_consent,
    is_cloud_consent_granted,
    revoke_cloud_consent,
)


def _config_path(tmp_path: Path) -> Path:
    """테스트용 설정 파일 경로 (상위 폴더는 일부러 만들지 않는다 — 자동 생성도 검증)."""
    return tmp_path / CONFIG_DIR_NAME / CONFIG_FILENAME


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_default_config_path_is_home_corpbrain_config_json() -> None:
    """기본 경로는 `~/.corpbrain/config.json` (스펙 §4.2). 경로 계산만 하고 I/O는 없다."""
    assert default_config_path() == Path.home() / ".corpbrain" / "config.json"


def test_grant_creates_file_with_spec_schema(tmp_path: Path) -> None:
    path = _config_path(tmp_path)

    grant_cloud_consent(config_path=path)

    assert path.exists()
    document = _read(path)
    assert document[CONSENT_KEY][CONSENT_PROVIDER]["granted"] is True
    assert isinstance(document[CONSENT_KEY][CONSENT_PROVIDER]["granted_at"], str)


def test_granted_at_is_iso8601_utc(tmp_path: Path) -> None:
    path = _config_path(tmp_path)

    grant_cloud_consent(config_path=path)

    granted_at = _read(path)[CONSENT_KEY][CONSENT_PROVIDER]["granted_at"]
    parsed = datetime.fromisoformat(granted_at)  # ISO8601로 파싱 가능해야 한다
    assert parsed.utcoffset() == timedelta(0)  # UTC


def test_grant_makes_consent_granted(tmp_path: Path) -> None:
    path = _config_path(tmp_path)

    grant_cloud_consent(config_path=path)

    assert is_cloud_consent_granted(config_path=path) is True


def test_revoke_makes_consent_not_granted(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    grant_cloud_consent(config_path=path)

    revoke_cloud_consent(config_path=path)

    assert is_cloud_consent_granted(config_path=path) is False
    assert _read(path)[CONSENT_KEY][CONSENT_PROVIDER]["granted"] is False


def test_grant_and_revoke_are_idempotent(tmp_path: Path) -> None:
    path = _config_path(tmp_path)

    grant_cloud_consent(config_path=path)
    grant_cloud_consent(config_path=path)
    assert is_cloud_consent_granted(config_path=path) is True

    revoke_cloud_consent(config_path=path)
    revoke_cloud_consent(config_path=path)
    assert is_cloud_consent_granted(config_path=path) is False


def test_revoke_without_existing_file_is_not_granted(tmp_path: Path) -> None:
    """한 번도 grant 하지 않은 상태에서 revoke 해도 실패하지 않는다 (사후 상태는 '동의 없음')."""
    path = _config_path(tmp_path)

    revoke_cloud_consent(config_path=path)

    assert is_cloud_consent_granted(config_path=path) is False


def test_grant_preserves_other_top_level_keys(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"other_setting": {"kept": 1}, "theme": "dark"}, ensure_ascii=False),
        encoding="utf-8",
    )

    grant_cloud_consent(config_path=path)

    document = _read(path)
    assert document["other_setting"] == {"kept": 1}
    assert document["theme"] == "dark"
    assert document[CONSENT_KEY][CONSENT_PROVIDER]["granted"] is True


def test_revoke_preserves_other_top_level_keys(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"other_setting": {"kept": 1}}), encoding="utf-8")
    grant_cloud_consent(config_path=path)

    revoke_cloud_consent(config_path=path)

    document = _read(path)
    assert document["other_setting"] == {"kept": 1}
    assert document[CONSENT_KEY][CONSENT_PROVIDER]["granted"] is False


def test_grant_preserves_other_providers_under_cloud_consent(tmp_path: Path) -> None:
    """`cloud_consent` 아래 다른 provider 항목도 보존한다 (후속 확장 이음새)."""
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({CONSENT_KEY: {"someone_else": {"granted": True}}}), encoding="utf-8"
    )

    grant_cloud_consent(config_path=path)

    document = _read(path)
    assert document[CONSENT_KEY]["someone_else"] == {"granted": True}
    assert document[CONSENT_KEY][CONSENT_PROVIDER]["granted"] is True


def test_missing_file_is_not_granted(tmp_path: Path) -> None:
    assert is_cloud_consent_granted(config_path=_config_path(tmp_path)) is False


def test_corrupted_json_is_not_granted(tmp_path: Path) -> None:
    """손상된 JSON은 예외가 아니라 '동의 없음'으로 수렴한다."""
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('{"cloud_consent": {"anthropic": {"granted": tru', encoding="utf-8")

    assert is_cloud_consent_granted(config_path=path) is False


def test_non_object_json_is_not_granted(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")

    assert is_cloud_consent_granted(config_path=path) is False


def test_grant_over_corrupted_file_records_consent(tmp_path: Path) -> None:
    """손상된 파일이 있어도 grant는 성공하고 결과는 유효한 JSON이다."""
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("not json at all", encoding="utf-8")

    grant_cloud_consent(config_path=path)

    assert is_cloud_consent_granted(config_path=path) is True
    assert _read(path)[CONSENT_KEY][CONSENT_PROVIDER]["granted"] is True


@pytest.mark.parametrize(
    "provider_entry",
    [
        {"granted": False},
        {"granted": "true"},  # 문자열은 동의로 취급하지 않는다
        {"granted": 1},
        {},  # granted 키 자체가 없음
        "granted",  # provider 항목이 객체가 아님
    ],
)
def test_only_boolean_true_counts_as_granted(tmp_path: Path, provider_entry: Any) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({CONSENT_KEY: {CONSENT_PROVIDER: provider_entry}}), encoding="utf-8"
    )

    assert is_cloud_consent_granted(config_path=path) is False


def test_unreadable_file_is_not_granted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """읽기 권한 없음(OSError)도 예외 전파 없이 '동의 없음'으로 취급한다."""
    path = _config_path(tmp_path)
    grant_cloud_consent(config_path=path)

    def deny(*args: object, **kwargs: object) -> str:
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "read_text", deny)

    assert is_cloud_consent_granted(config_path=path) is False


def test_atomic_write_leaves_no_temp_file(tmp_path: Path) -> None:
    """원자적 쓰기 후 디렉터리에는 설정 파일만 남는다 (임시 파일 잔여물 없음)."""
    path = _config_path(tmp_path)

    grant_cloud_consent(config_path=path)
    revoke_cloud_consent(config_path=path)
    grant_cloud_consent(config_path=path)

    assert [entry.name for entry in path.parent.iterdir()] == [CONFIG_FILENAME]


def test_write_failure_raises_consent_store_error(tmp_path: Path) -> None:
    """설정 폴더를 만들 수 없으면 조용히 넘어가지 않고 선행 조건 실패로 올린다."""
    blocker = tmp_path / CONFIG_DIR_NAME
    blocker.write_text("나는 폴더가 아니라 파일이다", encoding="utf-8")

    with pytest.raises(ConsentStoreError):
        grant_cloud_consent(config_path=blocker / CONFIG_FILENAME)


def test_config_file_never_contains_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API 키는 이 파일에 절대 쓰지 않는다 (스펙 §4.2·§4.1 — 환경변수로만 받는다)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-should-never-be-persisted")
    path = _config_path(tmp_path)

    grant_cloud_consent(config_path=path)

    raw = path.read_text(encoding="utf-8")
    assert "sk-ant-test-should-never-be-persisted" not in raw
    assert "ANTHROPIC_API_KEY" not in raw
    assert "api_key" not in raw
    assert set(_read(path)[CONSENT_KEY][CONSENT_PROVIDER]) == {"granted", "granted_at"}


# --- 갱신 시 기존 내용 보호 (코드 리뷰 후속) ---------------------------------------


def test_unreadable_file_is_not_silently_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """읽지 못한 파일을 덮어써 다른 키를 날리지 않는다 — 실패로 알린다.

    권한 거부·파일 잠금은 '내용이 없다'가 아니라 '내용을 확인하지 못했다'이므로,
    빈 문서로 덮어쓰면 멀쩡한 설정이 사라진다 (스펙 §4.2의 "다른 키는 보존" 이음새).
    """
    path = tmp_path / "config.json"
    path.write_text('{"other_setting": "소중한 값"}', encoding="utf-8")

    def _deny(*_args: object, **_kwargs: object) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", _deny)

    with pytest.raises(ConsentStoreError):
        grant_cloud_consent(config_path=path)


def test_unreadable_file_keeps_its_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """갱신이 거부된 뒤에도 원본 파일은 그대로 남아 있다."""
    path = tmp_path / "config.json"
    original = '{"other_setting": "소중한 값"}'
    path.write_text(original, encoding="utf-8")
    real_read = Path.read_text

    def _deny(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError(13, "Permission denied")
        return real_read(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", _deny)
    with pytest.raises(ConsentStoreError):
        revoke_cloud_consent(config_path=path)

    monkeypatch.undo()
    assert path.read_text(encoding="utf-8") == original


def test_missing_file_still_creates_a_fresh_document(tmp_path: Path) -> None:
    """'파일 없음'은 여전히 정상 경로다 — 새로 만든다(멱등)."""
    path = tmp_path / "nested" / "config.json"

    grant_cloud_consent(config_path=path)

    assert is_cloud_consent_granted(config_path=path) is True


def test_corrupt_json_is_still_overwritten(tmp_path: Path) -> None:
    """내용을 해석할 수 없으면 보존할 대상이 없으므로 덮어쓴다 (기존 결정 유지)."""
    path = tmp_path / "config.json"
    path.write_text("{ 깨진 JSON", encoding="utf-8")

    grant_cloud_consent(config_path=path)

    assert is_cloud_consent_granted(config_path=path) is True


def test_lookup_still_fails_safe_on_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """조회는 여전히 예외를 내지 않고 '동의 없음'으로 안전하게 실패한다."""
    path = tmp_path / "config.json"
    path.write_text('{"cloud_consent": {"anthropic": {"granted": true}}}', encoding="utf-8")

    def _deny(*_args: object, **_kwargs: object) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", _deny)

    assert is_cloud_consent_granted(config_path=path) is False
