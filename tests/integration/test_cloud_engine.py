"""클라우드 옵트인 통합 테스트 (v0.5 스펙 §3 완료의 정의 1~6·8~11).

Anthropic·Ollama HTTP는 단일 관문(`gateway.request_json`)을 스텁하고, `run_scan`을 코어 API로
직접 호출한다 — 실제 API에는 접속하지 않는다. 동의 설정 파일은 `Path.home()`을 tmp로 돌려
사용자 홈을 오염시키지 않는다.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import (
    DEFAULT_CLOUD_MODEL,
    DEFAULT_EMBED_MODEL,
    DEFAULT_MODEL,
    ENGINE_CLOUD,
    ENGINE_LOCAL,
    ScanConfig,
)
from corpbrain.core.consent import grant_cloud_consent, revoke_cloud_consent
from corpbrain.core.errors import PreconditionError
from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR, SUMMARY_TOOL_NAME
from corpbrain.core.models import SkipReason
from corpbrain.core.pipeline import run_scan
from corpbrain.core.rerun import read_engine

TAGS_RESPONSE = {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}

#: 스펙 §4.5의 7종을 모두 심은 원문. 마스킹이 걸리지 않으면 이 값들이 payload에 그대로 나간다.
PII_SAMPLES = {
    "RRN": "900101-1234567",
    "PHONE": "010-1234-5678",
    "EMAIL": "hong@example.com",
    "BIZ_NO": "123-45-67890",
    "CARD": "4111-1111-1111-1111",
    "ACCOUNT": "110-234-567890",
    "IP": "192.168.0.1",
}


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """동의 설정 파일을 tmp 홈으로 격리한다 — 실제 `~/.corpbrain`을 건드리지 않는다."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, "sk-test-key")


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.txt").write_text("첫 번째 문서 본문", encoding="utf-8")
    (folder / "b.txt").write_text("두 번째 문서 본문", encoding="utf-8")
    return folder


def _cloud_config(corpus: Path, tmp_path: Path, **overrides: Any) -> ScanConfig:
    params: dict[str, Any] = {
        "folder": corpus,
        "out_dir": tmp_path / "wiki",
        "engine": ENGINE_CLOUD,
        "force_gates": True,  # 토큰 게이트는 엔진과 무관하므로 소규모 픽스처에서 잡음을 없앤다
    }
    params.update(overrides)
    return ScanConfig(**params)


def _tool_use_response(text: str) -> dict[str, Any]:
    """Anthropic Messages의 강제된 tool_use 응답을 흉내낸다."""
    return {
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": SUMMARY_TOOL_NAME,
                "input": {
                    "title": f"제목: {text[:20]}",
                    "one_line_summary": "한 줄 요약",
                    "key_points": ["가", "나", "다"],
                    "summary": "문단 요약",
                    "tags": ["태그"],
                },
            }
        ],
    }


class _CloudGateway:
    """관문 스텁 — 목적지별로 응답을 나누고 나간 payload를 모두 붙잡아 둔다."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.payloads: list[Any] = []
        self.messages_error: Exception | None = None

    def __call__(self, url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        self.urls.append(url)
        self.payloads.append(payload)
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2]}
        if url.endswith("/v1/models"):
            return {"data": [{"id": DEFAULT_CLOUD_MODEL}]}
        if url.endswith("/v1/messages"):
            if self.messages_error is not None:
                raise self.messages_error
            return _tool_use_response(payload["messages"][0]["content"])
        raise AssertionError(f"예상하지 못한 목적지: {url}")

    @property
    def sent_text(self) -> str:
        """클라우드로 실제로 나간 모든 요청 본문을 이어붙인 문자열."""
        return json.dumps(
            [p for p in self.payloads if p is not None], ensure_ascii=False
        )


@pytest.fixture
def cloud_gateway(monkeypatch: pytest.MonkeyPatch) -> _CloudGateway:
    stub = _CloudGateway()
    monkeypatch.setattr(gateway, "request_json", stub)
    return stub


# --- §3 항목1·2·3: 동의 게이트 -------------------------------------------------


def test_scan_without_consent_fails_before_processing(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """항목2: 동의가 없으면 파일을 하나도 처리하지 않고 선행 조건 실패로 종료한다."""
    with pytest.raises(PreconditionError) as excinfo:
        run_scan(_cloud_config(corpus, tmp_path))

    assert "consent cloud --grant" in str(excinfo.value)
    assert not (tmp_path / "wiki").exists()
    assert cloud_gateway.urls == []  # 네트워크를 열기 전에 막힌다


def test_scan_proceeds_after_consent_is_granted(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """항목1: `consent --grant` 뒤에는 동의 확인 단계를 통과해 정상 처리된다."""
    grant_cloud_consent()

    result = run_scan(_cloud_config(corpus, tmp_path))

    assert len(result.generated) == 2


def test_revoke_blocks_cloud_again(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """항목3: 철회하면 다시 항목2와 동일하게 실패한다."""
    grant_cloud_consent()
    revoke_cloud_consent()

    with pytest.raises(PreconditionError):
        run_scan(_cloud_config(corpus, tmp_path))


# --- §3 항목4: 인증 프리플라이트 ------------------------------------------------


def test_missing_api_key_fails_before_processing(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """항목4: API 키가 없으면 산출물 0개로 선행 조건 실패."""
    grant_cloud_consent()
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)

    with pytest.raises(PreconditionError) as excinfo:
        run_scan(_cloud_config(corpus, tmp_path))

    assert API_KEY_ENV_VAR in str(excinfo.value)
    assert not (tmp_path / "wiki").exists()


def test_unauthorized_preflight_fails_before_processing(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """항목4: 프리플라이트가 401을 받으면 파일을 하나도 처리하지 않는다."""
    grant_cloud_consent()

    def _unauthorized(url: str, **kwargs: Any) -> Any:
        if url.endswith("/v1/models"):
            raise gateway.GatewayError("외부 호출이 HTTP 401로 실패했습니다", url=url)
        return cloud_gateway(url, **kwargs)

    monkeypatch.setattr(gateway, "request_json", _unauthorized)

    with pytest.raises(PreconditionError):
        run_scan(_cloud_config(corpus, tmp_path))

    assert not (tmp_path / "wiki").exists()


def test_preflight_runs_before_any_summary_call(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """프리플라이트(`/v1/models`)는 첫 요약(`/v1/messages`)보다 먼저 나간다."""
    grant_cloud_consent()

    run_scan(_cloud_config(corpus, tmp_path))

    assert cloud_gateway.urls.index("https://api.anthropic.com/v1/models") < (
        cloud_gateway.urls.index("https://api.anthropic.com/v1/messages")
    )


# --- §3 항목5: front-matter engine ---------------------------------------------


def test_cloud_wiki_records_engine_and_model(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """항목5: 생성물 front-matter에 engine=cloud와 실제 클라우드 모델이 남는다."""
    grant_cloud_consent()

    result = run_scan(_cloud_config(corpus, tmp_path))

    markdown = result.generated[0].output_path.read_text(encoding="utf-8")
    assert 'engine: "cloud"' in markdown
    assert f'model: "{DEFAULT_CLOUD_MODEL}"' in markdown


# --- §3 항목6: PII 마스킹 -------------------------------------------------------


def test_pii_never_leaves_the_gateway(
    tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """항목6: 7종을 심은 문서를 처리해도 관문 밖으로 나간 payload에 원본 PII가 없다."""
    grant_cloud_consent()
    folder = tmp_path / "docs"
    folder.mkdir()
    body = "\n".join(f"{name}: {value}" for name, value in PII_SAMPLES.items())
    (folder / "pii.txt").write_text(body, encoding="utf-8")

    result = run_scan(_cloud_config(folder, tmp_path))

    sent = cloud_gateway.sent_text
    for name, value in PII_SAMPLES.items():
        assert value not in sent, f"{name} 원문이 외부로 나갔다: {value}"
        assert f"[REDACTED_{name}]" in sent
    assert len(result.generated) == 1  # 위키 자체는 정상 생성된다


def test_pii_maskings_are_reported(tmp_path: Path, cloud_gateway: _CloudGateway) -> None:
    """마스킹 건수가 파일별로 결과에 집계된다 (§4.5)."""
    grant_cloud_consent()
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "pii.txt").write_text("연락처 010-1234-5678", encoding="utf-8")

    result = run_scan(_cloud_config(folder, tmp_path))

    assert len(result.pii_maskings) == 1
    assert result.pii_maskings[0].total == 1
    assert result.pii_maskings[0].counts == {"PHONE": 1}


def test_local_engine_does_not_mask_or_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """로컬 엔진은 외부로 나가지 않으므로 마스킹하지 않는다 (§4.5)."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "pii.txt").write_text("연락처 010-1234-5678", encoding="utf-8")
    sent: list[Any] = []

    def _local(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        sent.append(payload)
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2]}
        return {"response": json.dumps(_tool_use_response("x")["content"][0]["input"])}

    monkeypatch.setattr(gateway, "request_json", _local)

    result = run_scan(
        ScanConfig(folder=folder, out_dir=tmp_path / "wiki", force_gates=True)
    )

    assert result.pii_maskings == []
    assert "010-1234-5678" in json.dumps(
        [p for p in sent if p is not None], ensure_ascii=False
    )


# --- §3 항목8: 429/기타 오류 매핑 -----------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, SkipReason.CLOUD_RATE_LIMITED),
        (500, SkipReason.CLOUD_API_ERROR),
        (404, SkipReason.CLOUD_API_ERROR),
        (400, SkipReason.CLOUD_API_ERROR),
    ],
)
def test_cloud_failures_map_to_skip_reasons(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway,
    status: int, expected: SkipReason,
) -> None:
    """항목8: 429만 rate_limited, 나머지는 전부 api_error로 스킵되고 실행은 계속된다."""
    grant_cloud_consent()
    http_error = urllib.error.HTTPError(
        "https://api.anthropic.com/v1/messages", status, "err", {}, None  # type: ignore[arg-type]
    )
    wrapped = gateway.GatewayError("실패", url="https://api.anthropic.com/v1/messages")
    wrapped.__cause__ = http_error
    cloud_gateway.messages_error = wrapped

    result = run_scan(_cloud_config(corpus, tmp_path))

    assert result.generated == []
    assert {skip.reason for skip in result.skipped} == {expected}
    assert len(result.skipped) == 2  # 첫 파일에서 멈추지 않고 나머지도 계속 처리한다


def test_timeout_maps_to_api_error_and_others_continue(
    tmp_path: Path, cloud_gateway: _CloudGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    """항목8: 특정 파일만 타임아웃이면 그 파일만 스킵되고 나머지는 정상 생성된다(부분 성공)."""
    grant_cloud_consent()
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "bad.txt").write_text("실패할 문서", encoding="utf-8")
    (folder / "good.txt").write_text("정상 문서", encoding="utf-8")

    def _selective(url: str, *, method: str = "GET", payload: Any = None, **kw: Any) -> Any:
        if url.endswith("/v1/messages") and "실패할 문서" in payload["messages"][0]["content"]:
            raise gateway.GatewayError("timed out", url=url)
        return cloud_gateway(url, method=method, payload=payload, **kw)

    monkeypatch.setattr(gateway, "request_json", _selective)

    result = run_scan(_cloud_config(folder, tmp_path))

    assert [w.source_path.name for w in result.generated] == ["good.txt"]
    assert [(s.path.name, s.reason) for s in result.skipped] == [
        ("bad.txt", SkipReason.CLOUD_API_ERROR)
    ]


# --- §3 항목9: 엔진 전환 시 강제 재생성 -----------------------------------------


def test_switching_engine_forces_regeneration(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """항목9: local로 만든 위키를 원문 변경 없이 cloud로 다시 스캔하면 재생성된다."""
    grant_cloud_consent()
    out_dir = tmp_path / "wiki"

    def _local(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2]}
        return {"response": json.dumps(_tool_use_response("local")["content"][0]["input"])}

    monkeypatch.setattr(gateway, "request_json", _local)
    local_result = run_scan(
        ScanConfig(folder=corpus, out_dir=out_dir, engine=ENGINE_LOCAL, force_gates=True)
    )
    wiki = local_result.generated[0].output_path
    assert read_engine(wiki) == ENGINE_LOCAL

    monkeypatch.setattr(gateway, "request_json", cloud_gateway)
    cloud_result = run_scan(_cloud_config(corpus, tmp_path, out_dir=out_dir))

    assert len(cloud_result.generated) == 2  # mtime은 그대로지만 엔진이 달라 재생성된다
    assert read_engine(wiki) == ENGINE_CLOUD


def test_same_engine_rerun_still_skips_by_mtime(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """항목9: 같은 엔진으로 재스캔하면 기존 mtime 규칙대로 스킵된다."""
    grant_cloud_consent()
    config = _cloud_config(corpus, tmp_path)
    run_scan(config)

    second = run_scan(config)

    assert second.generated == []
    assert {skip.reason for skip in second.skipped} == {SkipReason.UP_TO_DATE}


# --- §3 항목11: 게이트 상호작용 -------------------------------------------------


def test_cloud_skips_gpu_gate(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """항목11: GPU 미탐지 환경에서도 cloud는 차단되지 않는다 (§4.7)."""
    grant_cloud_consent()
    monkeypatch.setattr(
        "corpbrain.core.plan.detect_hardware",
        lambda: __import__(
            "corpbrain.core.models", fromlist=["HardwareInfo"]
        ).HardwareInfo(gpu=False, label="CPU"),
    )

    result = run_scan(_cloud_config(corpus, tmp_path, force_gates=False))

    assert len(result.generated) == 2


def test_local_still_blocked_by_gpu_gate(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """항목11: 같은 환경에서 local은 기존대로 GPU 게이트에 차단된다."""
    from corpbrain.core.errors import GpuGateError

    monkeypatch.setattr(gateway, "request_json", lambda url, **_: TAGS_RESPONSE)
    monkeypatch.setattr(
        "corpbrain.core.plan.detect_hardware",
        lambda: __import__(
            "corpbrain.core.models", fromlist=["HardwareInfo"]
        ).HardwareInfo(gpu=False, label="CPU"),
    )

    with pytest.raises(GpuGateError):
        run_scan(ScanConfig(folder=corpus, out_dir=tmp_path / "wiki"))


def test_cloud_still_enforces_token_gate(
    corpus: Path, tmp_path: Path, cloud_gateway: _CloudGateway
) -> None:
    """항목11: 토큰 게이트는 비용 보호 목적이라 cloud에도 그대로 적용된다 (§4.7)."""
    from corpbrain.core.errors import TokenBudgetExceededError

    grant_cloud_consent()

    with pytest.raises(TokenBudgetExceededError):
        run_scan(_cloud_config(corpus, tmp_path, force_gates=False, max_total_tokens=1))
