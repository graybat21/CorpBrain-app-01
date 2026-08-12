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
from corpbrain.core.config import ScanConfig
from corpbrain.core.llm.ollama_client import OllamaNotAvailableError, detect
from corpbrain.core.pipeline import run_scan

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
    """관문을 스텁한 정상 실행에서 localhost 외 연결 시도가 0건이다 (완료의 정의 6)."""

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": []}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)

    run_scan(ScanConfig(folder=FIXTURE_CORPUS, out_dir=tmp_path / "wiki"))

    assert watch_sockets.offenders(LOCALHOST_HOSTS) == []


def test_gateway_only_dials_the_given_localhost_url(watch_sockets: SocketWatcher) -> None:
    """관문 스텁 없이 detect가 실제로 여는 소켓은 지정한 localhost 주소뿐이다."""
    url = "http://127.0.0.1:11434"

    with pytest.raises(OllamaNotAvailableError):
        detect(url)

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
