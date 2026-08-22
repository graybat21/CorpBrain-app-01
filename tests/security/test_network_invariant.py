"""보안 불변식 — 실행 중 `--ollama-url`(localhost) 외 네트워크 연결 0 (FR-019 / 스펙 §3-6, §4.5).

실제 소켓 `connect`를 감시(패치)해 연결 목적지를 수집하되 실제로는 원격에 나가지 않게 막는다.
파이프라인 전 구간에서 localhost 외 목적지로의 연결 시도가 없음을 강제한다.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, ScanConfig
from corpbrain.core.llm.embed import EmbeddingError, embed
from corpbrain.core.llm.ollama_client import OllamaNotAvailableError, detect
from corpbrain.core.pipeline import run_scan
from corpbrain.core.plan import plan_scan

FIXTURE_CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "sample_corpus"
LOCALHOST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

SUMMARY_JSON = {
    "title": "제목",
    "one_line_summary": "한 줄",
    "key_points": ["a", "b", "c"],
    "summary": "요약",
    "tags": ["t"],
}


class SocketWatcher:
    """소켓 연결 목적지를 수집하는 감시 장치."""

    def __init__(self) -> None:
        self.addresses: list[tuple[str, int]] = []

    def record(self, address: Any) -> None:
        if isinstance(address, tuple) and len(address) >= 2:
            self.addresses.append((str(address[0]), int(address[1])))

    def offenders(self, allowed_hosts: frozenset[str]) -> list[tuple[str, int]]:
        return [addr for addr in self.addresses if addr[0] not in allowed_hosts]


@pytest.fixture
def watch_sockets(monkeypatch: pytest.MonkeyPatch) -> SocketWatcher:
    watcher = SocketWatcher()

    def _fake_connect(self: socket.socket, address: Any) -> None:
        watcher.record(address)
        raise ConnectionRefusedError("보안 감시: 실제 연결을 차단했습니다")

    def _fake_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        watcher.record(address)
        raise ConnectionRefusedError("보안 감시: 실제 연결을 차단했습니다")

    monkeypatch.setattr(socket.socket, "connect", _fake_connect)
    monkeypatch.setattr(socket, "create_connection", _fake_create_connection)
    return watcher


def _host_of(url: str) -> str:
    return urlsplit(url).hostname or ""


def test_pipeline_makes_no_non_localhost_connections(
    watch_sockets: SocketWatcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """관문을 스텁한 정상 실행(요약+임베딩 포함)에서 localhost 외 연결 시도가 0건이다.

    v0.4 스펙 §3 완료의 정의 9: 임베딩 API 호출을 포함해 모든 네트워크 호출이 단일 관문
    (`gateway.request_json`)을 경유하는지 검증한다 — 임베딩 엔드포인트가 실제로 호출됐음을
    `calls`로 확인해, 이 테스트가 임베딩 경로를 우회하지 않고 있음을 보장한다.
    """
    calls: list[str] = []

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        calls.append(url)
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2, 0.3]}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)

    result = run_scan(
        ScanConfig(folder=FIXTURE_CORPUS, out_dir=tmp_path / "wiki", force_gates=True)
    )

    assert watch_sockets.offenders(LOCALHOST_HOSTS) == []
    assert result.embedding_failures == []
    assert any(url.endswith("/api/embeddings") for url in calls)  # 임베딩 경로가 실제로 돎


def test_graph_stage_makes_no_non_localhost_connections(
    watch_sockets: SocketWatcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0.6 §3 항목8 — 그래프 빌드·「관련 문서」 주입 단계에서도 localhost 외 연결이 0건이다.

    그래프 계층은 네트워크 라이브러리를 직접 호출하지 않는다 (v0.6 §4.8). 그래프가 실제로
    만들어졌음을 함께 단언해, 이 테스트가 그래프 경로를 지나치지 않고 있음을 보장한다 —
    감시장치가 공허하게 통과하는 것을 막는 `test_watcher_flags_a_gateway_bypass`와 같은 취지다.
    """

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2, 0.3]}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)

    result = run_scan(
        ScanConfig(folder=FIXTURE_CORPUS, out_dir=tmp_path / "wiki", force_gates=True)
    )

    assert watch_sockets.offenders(LOCALHOST_HOSTS) == []
    assert result.graph is not None
    assert result.graph.stats is not None
    assert result.graph.stats.edges > 0  # 그래프 단계가 실제로 돌았다
    assert result.graph.injection_failures == []


def test_gateway_only_dials_the_given_localhost_url(watch_sockets: SocketWatcher) -> None:
    """관문 스텁 없이 detect가 실제로 여는 소켓은 지정한 localhost 주소뿐이다."""
    url = "http://127.0.0.1:11434"

    with pytest.raises(OllamaNotAvailableError):
        detect(url)

    assert watch_sockets.addresses  # 실제로 연결을 시도했다
    assert watch_sockets.offenders(LOCALHOST_HOSTS) == []
    assert all(host == _host_of(url) for host, _ in watch_sockets.addresses)


def test_embed_only_dials_the_given_localhost_url(watch_sockets: SocketWatcher) -> None:
    """관문 스텁 없이 embed()가 실제로 여는 소켓은 지정한 localhost 주소뿐이다 (v0.4 §3 항목9)."""
    url = "http://127.0.0.1:11434"

    with pytest.raises(EmbeddingError):
        embed("문서 요약 텍스트", DEFAULT_EMBED_MODEL, url)

    assert watch_sockets.addresses  # 실제로 연결을 시도했다
    assert watch_sockets.offenders(LOCALHOST_HOSTS) == []
    assert all(host == _host_of(url) for host, _ in watch_sockets.addresses)


def test_custom_localhost_port_is_the_only_target(watch_sockets: SocketWatcher) -> None:
    """`--ollama-url`을 다른 localhost 포트로 바꿔도 그 주소로만 연결한다(외부 호스트 하드코딩 부재)."""
    url = "http://127.0.0.1:9999"

    with pytest.raises(OllamaNotAvailableError):
        detect(url)

    assert {addr[1] for addr in watch_sockets.addresses} == {9999}
    assert watch_sockets.offenders(LOCALHOST_HOSTS) == []


def test_watcher_flags_a_gateway_bypass(watch_sockets: SocketWatcher) -> None:
    """관문을 우회해 외부로 직접 연결하면 감시 장치가 검출한다(회귀 방지 자기검증)."""
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 443))

    assert watch_sockets.offenders(LOCALHOST_HOSTS) == [("example.com", 443)]


def test_plan_scan_opens_no_sockets_and_bypasses_gateway(
    watch_sockets: SocketWatcher, tmp_path: Path
) -> None:
    """v0.2 완료의 정의 3: plan은 localhost 포함 어떤 소켓도 열지 않고 관문도 거치지 않는다.

    하드웨어 감지는 로컬 nvidia-smi subprocess만 쓰므로(소켓 아님) 이 실행에서 소켓 연결이
    전혀 없어야 하고, `gateway.requested_urls()`도 비어 있어야 한다.
    """
    gateway.reset_requested_urls()
    (tmp_path / "note.txt").write_text("본문", encoding="utf-8")
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4 stub")

    plan_scan(ScanConfig(folder=tmp_path))

    assert watch_sockets.addresses == []  # localhost 포함 0건
    assert gateway.requested_urls() == ()


# --- v0.5: 엔진별 목적지 불변식 (스펙 §3 항목7) --------------------------------

ANTHROPIC_HOSTS = frozenset({"api.anthropic.com"})


def test_cloud_run_reaches_only_the_allowlisted_host(
    watch_sockets: SocketWatcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0.5 항목7: `--engine cloud` 실행 중 목적지는 localhost(임베딩)와 allowlist 호스트뿐이다.

    임베딩은 엔진과 무관하게 로컬이므로(§2 비목표) localhost도 정상 목적지다. 여기서 잡고자
    하는 것은 "그 둘 외의 어떤 목적지도 없다"는 불변식이다.
    """
    from corpbrain.core.config import ENGINE_CLOUD
    from corpbrain.core.consent import grant_cloud_consent
    from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR, SUMMARY_TOOL_NAME

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.setenv(API_KEY_ENV_VAR, "sk-test")
    grant_cloud_consent()

    calls: list[str] = []

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        calls.append(url)
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2, 0.3]}
        if url.endswith("/v1/models"):
            return {"data": []}
        return {
            "stop_reason": "tool_use",
            "content": [
                {"type": "tool_use", "name": SUMMARY_TOOL_NAME, "input": SUMMARY_JSON}
            ],
        }

    monkeypatch.setattr(gateway, "request_json", _request_json)

    run_scan(
        ScanConfig(
            folder=FIXTURE_CORPUS,
            out_dir=tmp_path / "wiki",
            engine=ENGINE_CLOUD,
            force_gates=True,
        )
    )

    assert watch_sockets.offenders(LOCALHOST_HOSTS | ANTHROPIC_HOSTS) == []
    # 클라우드 경로가 실제로 돌았음을 확인 — 불변식이 공허하게 통과하지 않게 한다.
    assert any(url.endswith("/v1/messages") for url in calls)
    assert all(_host_of(url) in LOCALHOST_HOSTS | ANTHROPIC_HOSTS for url in calls)


def test_local_run_never_reaches_the_cloud_host(
    watch_sockets: SocketWatcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0.5 항목7: 기본(`--engine` 미지정) 실행은 v0.4까지와 동일하게 localhost 외 연결이 없다."""
    calls: list[str] = []

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        calls.append(url)
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2, 0.3]}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)

    run_scan(
        ScanConfig(folder=FIXTURE_CORPUS, out_dir=tmp_path / "wiki", force_gates=True)
    )

    assert watch_sockets.offenders(LOCALHOST_HOSTS) == []
    assert all(_host_of(url) in LOCALHOST_HOSTS for url in calls)


def test_gateway_blocks_a_cloud_call_to_a_wrong_host(watch_sockets: SocketWatcher) -> None:
    """NetworkGuard가 allowlist 밖 목적지를 소켓 이전에 막는다 (자기검증)."""
    with pytest.raises(gateway.NetworkGuardError):
        gateway.request_json(
            "https://evil.example.com/v1/messages",
            allowed_hosts=("api.anthropic.com",),
            require_https=True,
        )

    assert watch_sockets.addresses == []  # 소켓을 아예 열지 않았다
