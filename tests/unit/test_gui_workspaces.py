"""워크스페이스 레지스트리 단위 테스트 (v0.9 스펙 §4.5).

레지스트리는 **GUI만 아는 저장소**다 — 코어와 CLI는 워크스페이스 개념을 모른다.
경로는 언제나 절대경로이며, 쓰기는 `consent.py`의 원자적 교체 관용구를 계승한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from corpbrain.gui import workspaces as ws


def test_missing_registry_reads_as_empty(tmp_path: Path) -> None:
    """아직 만든 적이 없으면 빈 목록이다 — 오류가 아니다."""
    assert ws.load(tmp_path / "none.json") == []


def test_add_assigns_id_and_created_at(tmp_path: Path) -> None:
    registry = tmp_path / "workspaces.json"
    source = tmp_path / "docs"
    out = tmp_path / "wiki"
    source.mkdir()

    entry = ws.add(registry, name="인사자료", source_dir=source, out_dir=out)

    assert entry.id
    assert entry.name == "인사자료"
    assert entry.created_at.endswith("+00:00") or entry.created_at.endswith("Z")
    assert ws.load(registry) == [entry]


def test_paths_are_stored_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """상대경로를 받아도 절대경로로 저장한다 (§4.5).

    브라우저가 보낸 `./inbox`는 서버 프로세스의 cwd 기준으로 풀려 사용자가 의도하지 않은
    폴더를 가리킨다. 저장 시점에 한 번 확정한다.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    registry = tmp_path / "workspaces.json"

    entry = ws.add(registry, name="상대", source_dir=Path("docs"), out_dir=Path("wiki"))

    assert Path(entry.source_dir).is_absolute()
    assert Path(entry.out_dir).is_absolute()
    assert Path(entry.source_dir) == (tmp_path / "docs").resolve()


def test_duplicate_name_is_allowed_but_ids_differ(tmp_path: Path) -> None:
    """이름은 표시용이라 겹쳐도 된다. 식별은 `id`가 한다."""
    registry = tmp_path / "workspaces.json"
    (tmp_path / "a").mkdir()

    first = ws.add(registry, name="같은이름", source_dir=tmp_path / "a", out_dir=tmp_path / "w1")
    second = ws.add(registry, name="같은이름", source_dir=tmp_path / "a", out_dir=tmp_path / "w2")

    assert first.id != second.id
    assert len(ws.load(registry)) == 2


def test_remove_deletes_only_the_entry(tmp_path: Path) -> None:
    """목록에서만 지운다 — 위키·인덱스 파일은 건드리지 않는다 (§4.7)."""
    registry = tmp_path / "workspaces.json"
    (tmp_path / "a").mkdir()
    out = tmp_path / "wiki"
    out.mkdir()
    (out / "marker.md").write_text("남아 있어야 한다", encoding="utf-8")
    entry = ws.add(registry, name="지울것", source_dir=tmp_path / "a", out_dir=out)

    ws.remove(registry, entry.id)

    assert ws.load(registry) == []
    assert (out / "marker.md").exists()


def test_remove_unknown_id_raises(tmp_path: Path) -> None:
    with pytest.raises(ws.WorkspaceNotFoundError):
        ws.remove(tmp_path / "workspaces.json", "없는-id")


# --- last_options (§4.5 · grill T6) --------------------------------------------


def test_last_options_round_trip(tmp_path: Path) -> None:
    registry = tmp_path / "workspaces.json"
    (tmp_path / "a").mkdir()
    entry = ws.add(registry, name="opts", source_dir=tmp_path / "a", out_dir=tmp_path / "w")

    ws.save_options(registry, entry.id, {"model": "qwen2.5:3b-instruct", "max_files": 20})

    assert ws.load(registry)[0].last_options == {
        "model": "qwen2.5:3b-instruct",
        "max_files": 20,
    }


@pytest.mark.parametrize("volatile", ["force", "force_gates"])
def test_volatile_options_are_never_saved(tmp_path: Path, volatile: str) -> None:
    """`force`와 `force_gates`는 저장하지 않는다 (grill T6).

    둘 다 「이번 한 번만」의 성격이라 조용히 유지되면 놀란다 — 어제 켠 `force`가 오늘도
    켜져 있으면 전체 재요약이 돌아 LLM 비용이 예기치 않게 발생한다.
    """
    registry = tmp_path / "workspaces.json"
    (tmp_path / "a").mkdir()
    entry = ws.add(registry, name="opts", source_dir=tmp_path / "a", out_dir=tmp_path / "w")

    ws.save_options(registry, entry.id, {volatile: True, "model": "m"})

    assert ws.load(registry)[0].last_options == {"model": "m"}


# --- 쓰기 방식 (§4.5) -----------------------------------------------------------


def test_write_is_atomic_and_leaves_no_temp_files(tmp_path: Path) -> None:
    """임시 파일 → `os.replace` — 쓰기 도중 중단돼도 깨진 JSON이 남지 않는다."""
    registry = tmp_path / "workspaces.json"
    (tmp_path / "a").mkdir()

    ws.add(registry, name="원자적", source_dir=tmp_path / "a", out_dir=tmp_path / "w")

    assert json.loads(registry.read_text(encoding="utf-8"))
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == ["workspaces.json"]


def test_corrupt_registry_raises_instead_of_silently_emptying(tmp_path: Path) -> None:
    """손상된 목록을 빈 목록으로 보지 않는다 — 조용히 덮어쓰면 사용자의 목록이 사라진다.

    동의 파일(`consent.py`)이 읽기 실패를 「동의 없음」으로 수렴시키는 것과 방향이 다르다.
    거기서는 판정 불가가 **거부**로 기울어야 안전하지만, 여기서는 판정 불가를 빈 목록으로
    보면 다음 쓰기가 기존 목록을 지운다.
    """
    registry = tmp_path / "workspaces.json"
    registry.write_text("{ 깨진 JSON", encoding="utf-8")

    with pytest.raises(ws.WorkspaceStoreError):
        ws.load(registry)


def test_default_registry_path_lives_beside_the_consent_file() -> None:
    """설정 파일 두 개가 같은 폴더에 모인다 (§4.5)."""
    from corpbrain.core.consent import default_config_path

    assert ws.default_registry_path().parent == default_config_path().parent
    assert ws.default_registry_path().name == "workspaces.json"


# --- 폴더 탐색 (§4.7) -----------------------------------------------------------


def test_list_directories_returns_only_subdirectories(tmp_path: Path) -> None:
    """브라우저는 로컬 경로를 줄 수 없으므로 서버가 목록을 돌려준다 (§4.7)."""
    (tmp_path / "인사").mkdir()
    (tmp_path / "개발").mkdir()
    (tmp_path / "메모.txt").write_text("파일", encoding="utf-8")

    listing = ws.list_directories(tmp_path)

    assert [d.name for d in listing.entries] == ["개발", "인사"]
    assert listing.path == str(tmp_path.resolve())
    assert listing.parent == str(tmp_path.parent.resolve())


def test_list_directories_rejects_a_file(tmp_path: Path) -> None:
    target = tmp_path / "메모.txt"
    target.write_text("파일", encoding="utf-8")

    with pytest.raises(ws.WorkspaceStoreError):
        ws.list_directories(target)


def test_list_directories_at_a_root_has_no_parent(tmp_path: Path) -> None:
    """루트에서는 위로 갈 곳이 없다 — `parent`가 `None`이다."""
    root = Path(tmp_path.anchor)

    listing = ws.list_directories(root)

    assert listing.parent is None
