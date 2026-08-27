"""GUI 서버 ↔ 코어 배선과 상태코드 (v0.9 §4.3 · DoD 1).

CLI 어댑터 테스트와 같은 잣대다 — 이 파일은 **배선과 상태코드**만 본다. 정확 문자열·순수
판정은 `tests/unit/test_gui_*.py`가 단언한다 (§3 「검증 방식」).
"""

from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import environment
from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
from corpbrain.core.llm import ollama_client
from corpbrain.core.models import EdgeType, GraphEdge, GraphNode, HardwareInfo, NodeType
from corpbrain.gui.api import SESSION_COOKIE, GuiApp

PORT = 8765
AUTH = {"Host": f"127.0.0.1:{PORT}", "Cookie": f"{SESSION_COOKIE}=sess"}


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "wiki"


@pytest.fixture
def app(out_dir: Path) -> GuiApp:
    return GuiApp(out_dir=out_dir, token="tok", port=PORT, session_token="sess")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """환경 점검을 고정한다 — 어댑터 테스트는 데몬 상태와 무관해야 한다."""
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/ollama")
    monkeypatch.setattr(
        environment, "detect_hardware", lambda: HardwareInfo(gpu=True, label="GPU: X")
    )
    monkeypatch.setattr(
        ollama_client, "list_models", lambda *_a, **_k: ["qwen2.5:7b-instruct"]
    )


def _seed_graph(out_dir: Path) -> None:
    """그래프 DB를 실제 코어 저장소로 채운다 — 스텁이 아니라 배선을 본다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    store = SqliteGraphStore(graph_path_for(out_dir))
    try:
        store.replace_graph(
            [
                GraphNode(id="/docs/a.md", type=NodeType.DOCUMENT, label="A"),
                GraphNode(id="/docs/b.md", type=NodeType.DOCUMENT, label="B"),
                GraphNode(id="tag:인사", type=NodeType.TAG, label="인사"),
            ],
            [
                GraphEdge(src="/docs/a.md", dst="tag:인사", type=EdgeType.TAGGED_WITH),
                GraphEdge(src="/docs/b.md", dst="tag:인사", type=EdgeType.TAGGED_WITH),
            ],
        )
    finally:
        store.close()


def test_dashboard_reports_doctor_and_graph(app: GuiApp, out_dir: Path) -> None:
    _seed_graph(out_dir)

    body = app.handle("GET", "/api/dashboard", AUTH).json()

    assert body["out_dir"] == str(out_dir)
    assert body["doctor"]["installed"] is True
    assert body["doctor"]["hardware"] == {"gpu": True, "label": "GPU: X"}
    assert body["graph"]["documents"] == 2
    assert body["graph"]["tags"] == 1
    assert body["graph"]["nodes"] == 3
    assert body["graph"]["edges_by_type"]["TAGGED_WITH"] == 2


def test_dashboard_survives_a_missing_graph_db(app: GuiApp) -> None:
    """첫 실행 — 그래프 DB가 없어도 **Doctor 카드는 실제 값으로** 그려진다 (§5).

    선행 조건 실패는 상태코드가 아니라 그 절 안의 구조화된 상태 본문으로 나온다 (§4.3.2).
    """
    response = app.handle("GET", "/api/dashboard", AUTH)

    assert response.status == 200
    body = response.json()
    assert body["doctor"]["installed"] is True  # 다른 절은 살아 있다
    assert body["graph"]["error"] == "PreconditionError"
    assert "scan" in body["graph"]["message"]


def test_dashboard_opens_and_closes_the_store_per_request(
    app: GuiApp, out_dir: Path
) -> None:
    """요청마다 저장소를 열고 닫는다 (§4.4) — 커넥션을 요청 사이에 캐시하지 않는다.

    `ThreadingHTTPServer`는 요청마다 스레드가 다르고 코어의 sqlite 커넥션은
    `check_same_thread` 기본값으로 열린다. 캐시하면 **두 번째 요청부터**
    `sqlite3.ProgrammingError`(=버그, 500)가 난다. 스레드를 갈아 가며 두 번 부르면 그
    실패 모드가 그대로 재현되므로, 통과 자체가 「캐시하지 않았다」의 증거다.

    타이밍 의존이 아니다 — 두 호출은 순차이고 동기화 장치를 쓰지 않는다.
    """
    _seed_graph(out_dir)

    def _call() -> int:
        return app.handle("GET", "/api/dashboard", AUTH).status

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(_call).result()
    with ThreadPoolExecutor(max_workers=1) as pool:
        second = pool.submit(_call).result()

    assert (first, second) == (200, 200)


def test_dashboard_passes_core_defaults_to_diagnose(
    app: GuiApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUI는 값을 그대로 코어에 넘긴다 — 자체 기본값을 만들지 않는다 (§4.3.3)."""
    seen: dict[str, Any] = {}

    def _spy(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return environment.DoctorReport(
            installed=True, running=True, model=kwargs["model"], model_present=True,
            embed_model=kwargs["embed_model"], embed_model_present=True,
            available_models=[], hardware=HardwareInfo(gpu=False, label="CPU"),
            max_file_size=1, max_total_tokens=2,
        )

    monkeypatch.setattr("corpbrain.gui.api.diagnose", _spy)
    body = app.handle("GET", "/api/dashboard", AUTH).json()

    from corpbrain.core.config import (
        DEFAULT_EMBED_MODEL,
        DEFAULT_MODEL,
        DEFAULT_OLLAMA_URL,
    )

    assert seen["model"] == DEFAULT_MODEL
    assert seen["embed_model"] == DEFAULT_EMBED_MODEL
    assert seen["ollama_url"] == DEFAULT_OLLAMA_URL
    assert body["doctor"]["model"] == DEFAULT_MODEL
