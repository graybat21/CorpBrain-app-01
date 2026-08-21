"""임베딩 요청·파싱 단위테스트 (v0.4 스펙 §4.3).

실제 네트워크는 쓰지 않는다 — 단일 관문 `gateway.request_json`을 스텁한다.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.llm import embed as embed_module
from corpbrain.core.llm.embed import EmbeddingError, embed


@pytest.fixture
def stub_gateway(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def _fake_request_json(url: str, **kwargs: Any) -> Any:
        calls.append({"url": url, **kwargs})
        return {"embedding": [0.1, 0.2, 0.3]}

    monkeypatch.setattr(gateway, "request_json", _fake_request_json)
    return calls


def test_valid_response_becomes_float_list(stub_gateway: list[dict[str, Any]]) -> None:
    vector = embed("문서 요약 텍스트", model="nomic-embed-text", ollama_url="http://127.0.0.1:11434")

    assert vector == [0.1, 0.2, 0.3]
    assert all(isinstance(x, float) for x in vector)


def test_request_targets_embeddings_endpoint_on_given_url(
    stub_gateway: list[dict[str, Any]],
) -> None:
    embed("문서 요약 텍스트", model="nomic-embed-text", ollama_url="http://127.0.0.1:11434")

    assert len(stub_gateway) == 1
    call = stub_gateway[0]
    assert call["url"] == "http://127.0.0.1:11434/api/embeddings"
    assert call["method"] == "POST"
    assert call["payload"] == {"model": "nomic-embed-text", "prompt": "문서 요약 텍스트"}


def test_gateway_failure_becomes_embedding_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_request_json(url: str, **kwargs: Any) -> Any:
        raise gateway.GatewayError("연결 실패", url=url)

    monkeypatch.setattr(gateway, "request_json", _fake_request_json)

    with pytest.raises(EmbeddingError):
        embed("문서 요약 텍스트")


@pytest.mark.parametrize(
    "envelope",
    [
        {"embedding": "not-a-list"},
        {"embedding": []},
        {"embedding": [1, "x", 3]},
        {"no_embedding_field": True},
        ["not", "a", "dict"],
    ],
)
def test_malformed_response_becomes_embedding_error(
    monkeypatch: pytest.MonkeyPatch, envelope: Any
) -> None:
    monkeypatch.setattr(gateway, "request_json", lambda url, **kwargs: envelope)

    with pytest.raises(EmbeddingError):
        embed("문서 요약 텍스트")


def test_embed_module_is_network_pure() -> None:
    """v0.4 스펙 §4.4: 임베딩 클라이언트는 `shutil`/`subprocess`/`os`를 import 하지 않는다.

    `ollama_client`와 동일한 정적 검사(`test_detect_never_attempts_installation_or_provisioning`)를
    임베딩 모듈에도 적용한다 — 설치 감지는 `core/environment.py`만 담당한다.
    """
    forbidden = {"subprocess", "shutil", "os", "sys", "venv", "pip"}
    tree = ast.parse(Path(embed_module.__file__).read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported & forbidden == set()
