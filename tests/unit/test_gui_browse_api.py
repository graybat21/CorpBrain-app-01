"""단위 테스트 — 폴더 선택(디렉터리 열람) 엔드포인트 (v0.9 §4.3 표 · §4.5 · §5).

이 절의 요지는 **제한을 두지 않는다**는 것이다 — CLI가 `corpbrain scan /any/path`를 제한 없이
수행하므로 GUI만 좁히면 같은 코어의 두 어댑터가 다른 권한을 갖는다. 그래서 이 파일은 「무엇을
막는가」가 아니라 「막지 않는다」와 「읽지 못할 때 어떻게 보고하는가」를 단언한다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

import pytest

from corpbrain.gui.api import SESSION_COOKIE, GuiApp

PORT = 8765
AUTH: ClassVar = {"Host": f"127.0.0.1:{PORT}", "Cookie": f"{SESSION_COOKIE}=sess"}


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    (root / "인사").mkdir(parents=True)
    (root / "개발").mkdir()
    (root / ".숨김").mkdir()
    (root / "보고서.docx").write_bytes(b"x")
    (root / "메모.txt").write_text("x", encoding="utf-8")
    (root / "그림.png").write_bytes(b"x")  # 미지원 확장자
    return root


@pytest.fixture
def app(tmp_path: Path) -> GuiApp:
    return GuiApp(
        out_dir=tmp_path / "wiki", token="tok", port=PORT, session_token="sess"
    )


def _browse(app: GuiApp, path: str | None = None) -> dict:
    query = f"?path={path}" if path is not None else ""
    return app.handle("GET", f"/api/browse{query}", AUTH).json()


def test_lists_subdirectories_of_an_arbitrary_absolute_path(
    app: GuiApp, tree: Path
) -> None:
    """§4.5 — 임의 절대경로를 열람할 수 있다. 허용 목록을 두지 않는다."""
    body = _browse(app, str(tree))

    assert body["path"] == str(tree.resolve())
    assert {entry["name"] for entry in body["directories"]} == {"인사", "개발", ".숨김"}


def test_files_are_not_listed_as_directories(app: GuiApp, tree: Path) -> None:
    body = _browse(app, str(tree))

    assert "보고서.docx" not in {entry["name"] for entry in body["directories"]}


def test_supported_file_count_uses_the_core_predicate(app: GuiApp, tree: Path) -> None:
    """폴더를 고르는 화면이므로 「여기 스캔할 것이 있는가」를 함께 낸다.

    판정은 코어 `is_supported()`가 한다 — 확장자 목록을 어댑터가 다시 적으면
    `SUPPORTED_EXTENSIONS`와 갈린다. `.png`는 세지 않는다.
    """
    body = _browse(app, str(tree))

    assert body["supported_file_count"] == 2  # .docx · .txt (.png 제외)


def test_hidden_entries_are_flagged_not_filtered(app: GuiApp, tree: Path) -> None:
    """서버가 거르지 않는다 — 「제한을 두지 않는다」가 거르는 쪽으로 새지 않게 한다."""
    body = _browse(app, str(tree))

    hidden = {entry["name"]: entry["hidden"] for entry in body["directories"]}
    assert hidden[".숨김"] is True
    assert hidden["인사"] is False


def test_parent_lets_the_screen_walk_up(app: GuiApp, tree: Path) -> None:
    body = _browse(app, str(tree))

    assert body["parent"] == str(tree.resolve().parent)


def test_root_reports_no_parent(app: GuiApp) -> None:
    """루트에서는 `parent`가 자기 자신이므로 `None`으로 내려 화면이 「위로」를 감춘다."""
    assert _browse(app, "/")["parent"] is None


def test_default_path_is_home_not_the_server_cwd(app: GuiApp) -> None:
    """서버를 어디서 띄웠느냐에 따라 첫 화면이 달라지지 않는다."""
    body = _browse(app)

    assert body["path"] == str(Path.home().resolve())


def test_tilde_is_expanded(app: GuiApp) -> None:
    assert _browse(app, "~")["path"] == str(Path.home().resolve())


class TestUnreadable:
    """§5 — 권한 거부를 그대로 보고하고 서버를 죽이지 않는다."""

    def _app(self, tmp_path: Path) -> GuiApp:
        return GuiApp(
            out_dir=tmp_path / "wiki", token="tok", port=PORT, session_token="sess"
        )

    def test_missing_path_is_a_domain_state(self, tmp_path: Path) -> None:
        response = self._app(tmp_path).handle(
            "GET", f"/api/browse?path={tmp_path}/없음", AUTH
        )

        # 사용자가 없는 경로를 눌러 본 것은 버그가 아니다 — 500이 되면 안 된다.
        assert response.status == 200
        assert response.json()["error"] == "DirectoryUnreadable"

    def test_a_file_is_a_domain_state(self, tmp_path: Path) -> None:
        target = tmp_path / "파일.txt"
        target.write_text("x", encoding="utf-8")

        body = self._app(tmp_path).handle("GET", f"/api/browse?path={target}", AUTH).json()

        assert body["error"] == "DirectoryUnreadable"

    @pytest.mark.skipif(os.geteuid() == 0, reason="root는 권한 거부를 만들 수 없다")
    def test_permission_denied_is_reported_not_raised(self, tmp_path: Path) -> None:
        locked = tmp_path / "잠김"
        locked.mkdir()
        locked.chmod(0o000)
        try:
            response = self._app(tmp_path).handle(
                "GET", f"/api/browse?path={locked}", AUTH
            )
        finally:
            locked.chmod(0o755)

        assert response.status == 200
        assert response.json()["error"] == "DirectoryUnreadable"

    def test_an_unreadable_child_does_not_fail_the_whole_listing(
        self, tmp_path: Path
    ) -> None:
        """항목 하나를 판정하지 못했다고 나열 전체를 실패시키지 않는다 (v0.1 §5)."""
        (tmp_path / "정상").mkdir()
        (tmp_path / "깨진링크").symlink_to(tmp_path / "없는대상")

        body = self._app(tmp_path).handle("GET", f"/api/browse?path={tmp_path}", AUTH).json()

        assert "정상" in {entry["name"] for entry in body["directories"]}
