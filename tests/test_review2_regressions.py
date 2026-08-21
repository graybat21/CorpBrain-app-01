"""2차 코드 리뷰 후속 회귀 테스트 — 각 수정이 되돌아가지 않게 고정한다.

A그룹 6건(감사 누락·생략 사유·게이트 표시·쓰기 예외·경로 이음새·front-matter 범위)과
B그룹 3건(관문 목적지 필수 선언·재실행 판정 순서)을 다룬다. B그룹의 import 방향 정리는
동작 변경이 없어 별도 테스트 대신 정적 검사(`test_gateway.py`)로 지킨다.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Self

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import (
    DEFAULT_CLOUD_MODEL,
    DEFAULT_MODEL,
    ENGINE_CLOUD,
    ENGINE_LOCAL,
    ScanConfig,
)
from corpbrain.core.consent import ConsentStoreError, grant_cloud_consent
from corpbrain.core.errors import PreconditionError
from corpbrain.core.llm import anthropic_client as ac
from corpbrain.core.llm.base import LLMParseError
from corpbrain.core.models import HardwareInfo, IndexingSkipReason, ScanResult
from corpbrain.core.pipeline import run_scan
from corpbrain.core.plan import plan_scan
from corpbrain.core.report import (
    build_plan_report_lines,
    build_scan_banner_lines,
    build_summary_lines,
)
from corpbrain.core.rerun import read_engine

SUMMARY_INPUT = {
    "title": "제목",
    "one_line_summary": "한 줄",
    "key_points": ["가"],
    "summary": "요약",
    "tags": ["t"],
}


# --- A-1: 파싱 실패해도 마스킹은 기록된다 -------------------------------------------


def test_masking_recorded_even_when_response_parsing_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """스키마 위반 응답이 와도 last_mask가 남는다 — 본문은 이미 전송된 뒤다 (§4.5·§3-16)."""
    monkeypatch.setattr(
        gateway,
        "request_json",
        lambda url, **_: {"stop_reason": "end_turn", "content": [{"type": "text"}]},
    )
    summarizer = ac.AnthropicSummarizer(DEFAULT_CLOUD_MODEL, "sk-test")

    with pytest.raises(LLMParseError):
        summarizer.summarize("연락처 010-1234-5678")

    assert summarizer.last_mask is not None
    assert summarizer.last_mask.total == 1


def test_masking_recorded_even_when_call_is_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """429로 거부돼도 요청은 나갔으므로 마스킹 기록을 남긴다."""

    def _boom(url: str, **_: Any) -> Any:
        raise gateway.GatewayError("429", url=url, status=429)

    monkeypatch.setattr(gateway, "request_json", _boom)
    summarizer = ac.AnthropicSummarizer(DEFAULT_CLOUD_MODEL, "sk-test")

    with pytest.raises(ac.CloudRateLimitedError):
        summarizer.summarize("주민번호 900101-1234567")

    assert summarizer.last_mask is not None
    assert summarizer.last_mask.total == 1


def test_masking_happens_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """마스킹은 호출자에서 한 번만 일어난다 — 전송 함수가 다시 마스킹하지 않는다.

    두 번 돌면 이미 치환된 플레이스홀더를 또 세어 집계가 부풀거나, 플레이스홀더 안의
    숫자열이 다시 걸려 전송본이 망가질 수 있다.
    """
    sent: list[str] = []

    def _capture(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if payload is not None and "messages" in payload:
            sent.append(payload["messages"][0]["content"])
        return {
            "stop_reason": "tool_use",
            "content": [
                {"type": "tool_use", "name": ac.SUMMARY_TOOL_NAME, "input": SUMMARY_INPUT}
            ],
        }

    monkeypatch.setattr(gateway, "request_json", _capture)
    summarizer = ac.AnthropicSummarizer(DEFAULT_CLOUD_MODEL, "sk-test")

    summarizer.summarize("연락처 010-1234-5678 입니다")

    assert summarizer.last_mask is not None
    assert summarizer.last_mask.total == 1  # 두 번 세지 않는다
    assert sent[0].count("[REDACTED_PHONE]") == 1


def test_failed_file_appears_in_the_masking_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """파싱 실패로 스킵된 파일도 감사 기록에 남는다 — 마스킹된 본문이 나갔기 때문이다."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.txt").write_text("연락처 010-1234-5678", encoding="utf-8")
    config_path = tmp_path / "config.json"
    grant_cloud_consent(config_path=config_path)
    monkeypatch.setenv(ac.API_KEY_ENV_VAR, "sk-test")

    def _bad_schema(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}]}
        if url.endswith("/v1/models"):
            return {"data": []}
        return {"stop_reason": "end_turn", "content": [{"type": "text"}]}

    monkeypatch.setattr(gateway, "request_json", _bad_schema)

    result = run_scan(
        ScanConfig(
            folder=folder,
            out_dir=tmp_path / "wiki",
            engine=ENGINE_CLOUD,
            force_gates=True,
        ),
        consent_path=config_path,
    )

    assert result.generated == []
    assert len(result.pii_maskings) == 1
    assert result.pii_maskings[0].counts == {"PHONE": 1}


# --- A-2: 인덱싱 생략 사유가 구분된다 -----------------------------------------------


@pytest.mark.parametrize(
    ("reason", "must_contain", "must_not_contain"),
    [
        (IndexingSkipReason.OLLAMA_UNAVAILABLE, "ollama serve", "ollama pull"),
        (IndexingSkipReason.EMBED_MODEL_MISSING, "ollama pull", "ollama serve"),
    ],
)
def test_indexing_skip_message_names_the_right_fix(
    reason: IndexingSkipReason, must_contain: str, must_not_contain: str
) -> None:
    """사유마다 해결 조치가 다르므로 안내도 갈라진다 (§4.8)."""
    result = ScanResult(out_dir=Path("wiki"), indexing_skip_reason=reason)

    summary = "\n".join(build_summary_lines(result))

    assert "인덱싱 생략" in summary
    assert must_contain in summary
    assert must_not_contain not in summary


def test_indexing_skipped_property_follows_the_reason() -> None:
    """indexing_skipped는 사유 유무에서 파생된다 — 두 값이 어긋날 수 없다."""
    assert ScanResult(out_dir=Path("w")).indexing_skipped is False
    assert (
        ScanResult(
            out_dir=Path("w"),
            indexing_skip_reason=IndexingSkipReason.OLLAMA_UNAVAILABLE,
        ).indexing_skipped
        is True
    )


# --- A-3: GPU 게이트 표시가 실제 차단 여부와 일치한다 --------------------------------


def _plan_for(engine: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    (tmp_path / "a.txt").write_text("본문", encoding="utf-8")
    monkeypatch.setattr(
        "corpbrain.core.plan.detect_hardware",
        lambda: HardwareInfo(gpu=False, label="CPU"),
    )
    return plan_scan(ScanConfig(folder=tmp_path, engine=engine))


def test_cloud_plan_does_not_claim_the_gpu_gate_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cloud는 GPU 게이트가 차단하지 않으므로 리포트도 '차단'이라 말하지 않는다 (§4.7)."""
    plan = _plan_for(ENGINE_CLOUD, tmp_path, monkeypatch)

    assert plan.gate is not None
    assert plan.gate.gpu_enforced is False
    assert "--force-gates 필요" not in "\n".join(build_plan_report_lines(plan, 50))
    assert "CPU(차단)" not in "\n".join(build_scan_banner_lines(plan))


def test_local_plan_still_reports_the_gpu_gate_as_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """로컬은 종전대로 차단으로 표시된다."""
    plan = _plan_for(ENGINE_LOCAL, tmp_path, monkeypatch)

    assert plan.gate is not None
    assert plan.gate.gpu_enforced is True
    assert "--force-gates 필요" in "\n".join(build_plan_report_lines(plan, 50))


# --- A-4: 쓰기 실패가 도메인 예외로 수렴한다 -----------------------------------------


class _BadHandle:
    """write에서 인코딩 오류를 내는 파일 핸들 스텁 (OSError가 아닌 실패)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def write(self, _payload: str) -> int:
        raise UnicodeEncodeError("utf-8", "x", 0, 1, "surrogates not allowed")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> bool:
        self._inner.close()
        return False


def test_encoding_failure_is_wrapped_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OSError가 아닌 실패도 ConsentStoreError로 감싸고 임시본을 남기지 않는다."""
    real_fdopen = os.fdopen
    monkeypatch.setattr(
        os, "fdopen", lambda fd, *a, **k: _BadHandle(real_fdopen(fd, *a, **k))
    )
    path = tmp_path / "config.json"

    with pytest.raises(ConsentStoreError):
        grant_cloud_consent(config_path=path)

    monkeypatch.undo()
    assert list(tmp_path.glob("*.tmp")) == []


# --- A-5: run_scan에 동의 경로 이음새가 있다 -----------------------------------------


def test_run_scan_accepts_a_consent_path_without_patching_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Path.home 전역 패치 없이도 동의 파일을 격리할 수 있다."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.txt").write_text("본문", encoding="utf-8")
    monkeypatch.setenv(ac.API_KEY_ENV_VAR, "sk-test")

    with pytest.raises(PreconditionError) as excinfo:
        run_scan(
            ScanConfig(folder=folder, out_dir=tmp_path / "wiki", engine=ENGINE_CLOUD),
            consent_path=tmp_path / "none.json",
        )

    assert "consent cloud --grant" in str(excinfo.value)


def test_run_scan_reads_consent_from_the_injected_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """주입한 경로의 동의가 실제로 인정된다(동의 단계를 통과한다)."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.txt").write_text("본문", encoding="utf-8")
    config_path = tmp_path / "config.json"
    grant_cloud_consent(config_path=config_path)
    monkeypatch.setenv(ac.API_KEY_ENV_VAR, "sk-test")

    def _stub(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}]}
        if url.endswith("/v1/models"):
            return {"data": []}
        return {
            "stop_reason": "tool_use",
            "content": [
                {"type": "tool_use", "name": ac.SUMMARY_TOOL_NAME, "input": SUMMARY_INPUT}
            ],
        }

    monkeypatch.setattr(gateway, "request_json", _stub)

    result = run_scan(
        ScanConfig(
            folder=folder,
            out_dir=tmp_path / "wiki",
            engine=ENGINE_CLOUD,
            force_gates=True,
        ),
        consent_path=config_path,
    )

    assert len(result.generated) == 1


# --- A-6: front-matter 밖은 읽지 않는다 ----------------------------------------------


def _wiki(body: str) -> Path:
    path = Path(tempfile.mkdtemp()) / "w.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_body_line_is_not_mistaken_for_the_recorded_engine() -> None:
    """본문이 engine: 으로 시작해도 front-matter 밖이면 무시한다."""
    wiki = _wiki(
        '---\nmodel: "m"\nsource_bytes: 1\n---\n\n## 요약\n'
        "engine: cloud 로 설정하면 외부 API를 쓰게 된다.\n"
    )

    assert read_engine(wiki) == ENGINE_LOCAL


def test_front_matter_value_wins_over_body() -> None:
    """front-matter에 값이 있으면 본문 주장과 무관하게 그 값을 쓴다."""
    wiki = _wiki(
        '---\nmodel: "m"\nengine: "cloud"\n---\n\n## 요약\n'
        "engine: local 이라고 본문이 주장해도\n"
    )

    assert read_engine(wiki) == ENGINE_CLOUD


def test_missing_front_matter_falls_back_to_local() -> None:
    """front-matter 자체가 없으면 로컬로 본다(v0.4 이전 생성물 하위 호환)."""
    assert read_engine(_wiki("# 제목만 있는 파일\n\n본문\n")) == ENGINE_LOCAL


# --- B-1: 관문 목적지 정책은 필수 선언이다 ------------------------------------------


def test_local_llm_calls_declare_their_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    """로컬 요약·임베딩·탐지 호출이 모두 --ollama-url 호스트를 관문에 선언한다 (§4.4)."""
    seen: list[Any] = []

    def _capture(url: str, *, allowed_hosts: Any, **_: Any) -> Any:
        seen.append(allowed_hosts)
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}]}
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1]}
        return {"response": '{"title":"t","one_line_summary":"o","key_points":["k"],'
                            '"summary":"s","tags":["g"]}'}

    monkeypatch.setattr(gateway, "request_json", _capture)

    from corpbrain.core.llm.embed import embed
    from corpbrain.core.llm.ollama_client import list_models
    from corpbrain.core.llm.summarize import summarize

    remote = "http://gpu-box.lan:11434"
    list_models(remote)
    summarize("본문", DEFAULT_MODEL, remote)
    embed("본문", "nomic-embed-text", remote)

    assert len(seen) == 3
    assert all(hosts == ("gpu-box.lan",) for hosts in seen)


def test_remote_ollama_host_passes_the_guard() -> None:
    """localhost가 아닌 Ollama도 가드를 통과한다 — LAN GPU 박스 사용을 막지 않는다 (C-1 결정)."""
    url = "http://gpu-box.lan:11434/api/tags"

    # 가드만 직접 확인한다(소켓을 열지 않는다). 예외가 없으면 통과다.
    gateway._guard_destination(
        url, allowed_hosts=(gateway.host_of(url),), require_https=False
    )


def test_guard_still_blocks_a_host_the_caller_did_not_declare() -> None:
    """선언하지 않은 목적지는 여전히 막힌다 — 자기참조 선언이 무제한을 뜻하지 않는다."""
    with pytest.raises(gateway.NetworkGuardError):
        gateway._guard_destination(
            "http://evil.example.com/api/tags",
            allowed_hosts=("gpu-box.lan",),
            require_https=False,
        )


def test_host_of_extracts_the_hostname() -> None:
    """host_of는 포트·경로·대소문자를 제거하고 호스트만 남긴다."""
    assert gateway.host_of("http://127.0.0.1:11434/api/tags") == "127.0.0.1"
    assert gateway.host_of("https://API.Anthropic.COM/v1/messages") == "api.anthropic.com"


# --- B-3: 값싼 판정이 먼저 온다 -------------------------------------------------------


def test_changed_source_does_not_read_the_existing_wiki(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mtime만으로 재생성이 확정되면 위키를 열어 읽지 않는다 (불필요한 I/O 제거)."""
    from corpbrain.core import rerun

    source = tmp_path / "a.txt"
    source.write_text("본문", encoding="utf-8")
    wiki = tmp_path / "a.txt.md"
    wiki.write_text('---\nengine: "local"\n---\n', encoding="utf-8")
    os.utime(wiki, (1, 1))  # 위키를 원문보다 과거로 만든다

    reads: list[Path] = []
    monkeypatch.setattr(
        rerun, "read_engine", lambda path: reads.append(path) or ENGINE_LOCAL
    )

    assert rerun.should_regenerate(source, wiki, engine=ENGINE_LOCAL) is True
    assert reads == []  # 열지 않았다


def test_engine_switch_still_forces_regeneration_when_mtime_is_stale(
    tmp_path: Path
) -> None:
    """원문이 그대로여도 엔진이 다르면 재생성한다 — 순서를 바꿔도 계약은 그대로다 (§3-9)."""
    from corpbrain.core.rerun import should_regenerate

    source = tmp_path / "a.txt"
    source.write_text("본문", encoding="utf-8")
    wiki = tmp_path / "a.txt.md"
    wiki.write_text('---\nengine: "local"\n---\n', encoding="utf-8")
    os.utime(source, (1, 1))  # 원문을 위키보다 과거로 만든다

    assert should_regenerate(source, wiki, engine=ENGINE_CLOUD) is True
    assert should_regenerate(source, wiki, engine=ENGINE_LOCAL) is False
