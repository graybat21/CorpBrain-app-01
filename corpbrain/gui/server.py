"""로컬 웹 GUI 서버 — 표준 라이브러리 `ThreadingHTTPServer` (v0.9 스펙 §4.2).

신규 런타임 의존성이 0개다. 게이트웨이가 세운 "서드파티 HTTP 의존성을 두지 않는다"를
그대로 잇는다.

**바인딩은 `127.0.0.1` 고정이며 플래그로 바꿀 수 없다** (§4.1). 보안 불변식 테스트가
localhost 외 목적지를 offender로 잡으므로 사실상 강제되는 값이고, 옵션으로 열어 두면 그
강제가 무의미해진다.

`127.0.0.1` 바인딩은 다른 머신만 막을 뿐 **같은 컴퓨터의 다른 프로그램과 브라우저의 다른
탭은 막지 못한다.** 이 서버는 로컬 파일시스템을 탐색하고 문서 본문을 그대로 돌려주므로,
랜덤 토큰과 `Host` 헤더 검증을 함께 둔다 (§4.6).
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import (  # 순수 문자열 처리 — 네트워크 아님
    parse_qs,
    unquote,
    urlencode,
    urlsplit,
)

from corpbrain import core
from corpbrain.core.config import API_KEY_ENV_VAR
from corpbrain.core.errors import PreconditionError
from corpbrain.core.graphstore import graph_path_for
from corpbrain.core.report import build_doctor_lines
from corpbrain.gui import markdown, runner, scanjob, workspaces

__all__ = [
    "DEFAULT_PORT",
    "HOST",
    "PORT_ATTEMPTS",
    "TOKEN_HEADER",
    "TOKEN_QUERY_KEY",
    "AuthFailure",
    "GuiState",
    "PortUnavailableError",
    "authorize",
    "create_server",
    "entry_url",
    "make_handler",
]

#: 바인딩 주소 — 고정값이다. `--host` 플래그를 두지 않는다 (§4.1).
HOST = "127.0.0.1"

#: 기본 포트. 사용 중이면 다음 빈 포트를 찾는다 (§5).
DEFAULT_PORT = 8765

#: 포트를 위로 몇 칸까지 시도하는가. 전부 실패하면 선행 조건 실패다.
PORT_ATTEMPTS = 20

#: 첫 진입(`GET /`)에서만 쓰는 쿼리스트링 키 (§4.6.1).
#: 이후 요청은 커스텀 헤더로 토큰을 싣는다 — 쿼리스트링은 서버 로그·브라우저 히스토리·
#: `Referer`에 남는다.
TOKEN_QUERY_KEY = "t"

#: 첫 진입 이후 모든 `/api/*` 요청이 토큰을 싣는 헤더 (§4.6.1).
#:
#: **커스텀 헤더여야 한다.** 쿠키를 쓰면 브라우저가 다른 탭에서 온 요청에도 자동으로 붙여
#: 보내 토큰을 둔 목적(CSRF 차단) 자체가 무효가 된다. 커스텀 헤더는 다른 출처가 붙일 수 없다.
TOKEN_HEADER = "X-CorpBrain-Token"

#: 토큰을 요구하는 경로 접두사. **이 접두사 밖은 전부 토큰 없이 받는다** — 페이지 껍데기와
#: 정적 자산이다.
#:
#: 브라우저는 `<link>`·`<script>` 요청에 커스텀 헤더를 붙일 수 없어 정적 자산을 토큰으로
#: 막을 수 없다. 그 경로들은 데이터를 담지 않으며, 데이터를 주는 `/api/*`가 막혀 있으므로
#: 안전하다.
API_PREFIX = "/api/"

#: 모델을 대신 지정할 수 있는 환경변수. **`corpbrain/cli.py`의 같은 이름 상수와 값이 같아야
#: 한다** — CLI 로 스캔하다 GUI 로 옮겨 왔을 때 같은 모델이 잡혀야 하기 때문이다.
#:
#: `cli` 를 import 해서 가져오지 않는다. `cli` 가 이 모듈을 import 하므로 순환이 된다.
#: 대신 `tests/test_gui_server.py` 가 두 값이 같음을 단언해 복제를 묶어 둔다.
MODEL_ENV_VAR = "CORPBRAIN_MODEL"
EMBED_MODEL_ENV_VAR = "CORPBRAIN_EMBED_MODEL"


def resolve_model(explicit: str | None) -> str:
    """모델 우선순위를 해소한다: 명시값 > 환경변수 > 코어 기본값.

    CLI 의 `_resolve_model()` 과 같은 규칙이다. 이것이 없으면 GUI 만 환경변수를 무시해,
    `CORPBRAIN_MODEL` 을 설정해 둔 사용자가 화면에서는 기본 모델이 점검·실행되는 것을 본다.
    """
    return (explicit or "").strip() or os.environ.get(MODEL_ENV_VAR, "").strip() or core.DEFAULT_MODEL


def resolve_embed_model(explicit: str | None) -> str:
    """임베딩 모델 우선순위를 해소한다: 명시값 > 환경변수 > 코어 기본값."""
    return (
        (explicit or "").strip()
        or os.environ.get(EMBED_MODEL_ENV_VAR, "").strip()
        or core.DEFAULT_EMBED_MODEL
    )


class PortUnavailableError(PreconditionError):
    """`PORT_ATTEMPTS` 범위에서 빈 포트를 찾지 못했다 — CLI가 exit 1로 매핑한다."""


@dataclass
class GuiState:
    """서버 프로세스가 살아 있는 동안의 상태.

    토큰은 **기동할 때마다 새로 만들고 파일에 저장하지 않는다** (§4.6).
    """

    #: 이 프로세스에서만 유효한 랜덤 토큰.
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    #: 워크스페이스 레지스트리 위치. 테스트가 홈 디렉터리를 건드리지 않도록 주입 가능하다.
    registry_path: Path = field(default_factory=workspaces.default_registry_path)
    #: 스캔 자식 프로세스 관리자. **전체에서 하나**다 (§5 — 동시 스캔 1개).
    jobs: scanjob.ScanJobManager = field(default_factory=scanjob.ScanJobManager)


@dataclass(frozen=True)
class AuthFailure:
    """요청을 거절한 이유. `None`이 «통과»다."""

    status: int
    detail: str


def allowed_hosts(port: int) -> frozenset[str]:
    """이 서버가 자기 것으로 인정하는 `Host` 헤더 값 (§4.6).

    포트까지 함께 본다 — DNS rebinding 은 이름을 우리 것으로 맞추므로 호스트 문자열만
    비교하면 통과할 수 있다.
    """
    return frozenset({f"{HOST}:{port}", f"localhost:{port}"})


def authorize(
    *,
    path: str,
    host: str | None,
    header_token: str | None,
    query_token: str | None,
    state: GuiState,
    port: int,
) -> AuthFailure | None:
    """요청을 받아들일지 판정한다 — 순수 함수다 (§4.6).

    두 관문을 차례로 통과해야 한다.

    1. **`Host` 헤더**가 `127.0.0.1:<port>` 또는 `localhost:<port>` 여야 한다. 아니면 403.
       토큰이 면제되는 경로에서도 이 검사는 살아 있다.
    2. **`/api/*` 는 `TOKEN_HEADER` 에 실린 토큰**을 요구한다. 없거나 틀리면 401.

    `query_token` 은 **첫 진입(`GET /`)에서만** 의미가 있다. API 가 쿼리 토큰을 받아 주면
    토큰이 서버 접근 로그와 `Referer` 헤더에 계속 남으므로 여기서 받지 않는다.
    """
    if host is None or host not in allowed_hosts(port):
        return AuthFailure(403, "허용되지 않은 Host 헤더입니다.")

    if not path.startswith(API_PREFIX):
        return None

    if header_token is None or not secrets.compare_digest(header_token, state.token):
        return AuthFailure(401, f"{TOKEN_HEADER} 헤더에 유효한 토큰이 필요합니다.")
    return None


def route(
    *,
    method: str,
    path: str,
    query: dict[str, list[str]],
    body: dict[str, Any],
    state: GuiState,
) -> tuple[int, dict[str, Any]]:
    """API 요청 하나를 처리해 `(상태코드, 응답 본문)`을 돌려준다.

    **HTTP 계층에서 분리된 순수 조립 함수다.** 테스트가 소켓 없이 직접 부를 수 있고,
    핸들러는 이 반환을 그대로 내보내기만 한다 — CLI 어댑터가 `report.py` 의 순수 함수 반환을
    출력만 하는 것과 같은 결이다.
    """
    try:
        return _route(method=method, path=path, query=query, body=body, state=state)
    except workspaces.WorkspaceNotFoundError as exc:
        return 404, {"error": str(exc)}
    except (workspaces.WorkspaceStoreError, PreconditionError) as exc:
        return 400, {"error": str(exc)}
    except sqlite3.Error as exc:
        # 스캔이 저장소를 잡고 있을 때 조회가 부딪칠 수 있다 (§5). 원시 트레이스백이
        # 500으로 새지 않게 안내로 바꾼다 — 현재 코어도 CLI도 이 예외를 잡지 않는다.
        return 503, {"error": f"저장소를 지금 읽을 수 없습니다: {exc} — 잠시 후 다시 시도하세요."}


def _route(
    *,
    method: str,
    path: str,
    query: dict[str, list[str]],
    body: dict[str, Any],
    state: GuiState,
) -> tuple[int, dict[str, Any]]:
    # 스캔
    if method == "POST" and path == "/api/scan":
        return _start_scan(body, state)
    if method == "GET" and path == "/api/scan":
        status = state.jobs.status()
        return (200, status) if status is not None else (200, {"running": False})
    if method == "DELETE" and path == "/api/scan":
        return 200, {"stopped": state.jobs.stop()}

    # 워크스페이스
    if method == "GET" and path == "/api/workspaces":
        return 200, {"workspaces": [asdict(e) for e in workspaces.load(state.registry_path)]}
    if method == "POST" and path == "/api/workspaces":
        return _add_workspace(body, state)
    # **하위 경로가 있으면 여기서 잡지 않는다.** `_scoped()`가 `None`일 때만 «워크스페이스
    # 자체를 지운다»는 뜻이다. 이 검사가 없으면 `DELETE .../{id}/index` 의 마지막 조각
    # (`index`)을 워크스페이스 id로 읽어 「그런 워크스페이스가 없습니다」로 답한다.
    if method == "DELETE" and path.startswith("/api/workspaces/") and _scoped(path) is None:
        workspaces.remove(state.registry_path, path.rsplit("/", 1)[-1])
        return 200, {"removed": True}

    # 폴더 탐색
    if method == "GET" and path == "/api/fs/list":
        raw = _first(query.get("path")) or str(Path.home())
        listing = workspaces.list_directories(Path(raw))
        return 200, {
            "path": listing.path,
            "parent": listing.parent,
            "entries": [{"name": p.name, "path": str(p)} for p in listing.entries],
        }

    # 설치된 모델 목록
    if method == "GET" and path == "/api/models":
        workspace_id = _first(query.get("workspace_id"))
        saved = _entry(state, workspace_id).last_options if workspace_id else {}
        return 200, _installed_models(saved)

    # 환경 점검
    if method == "GET" and path == "/api/doctor":
        return 200, _doctor_payload(query, state)

    # 클라우드 설정
    if method == "GET" and path == "/api/settings/cloud":
        return 200, _cloud_settings()
    if method == "PUT" and path == "/api/settings/cloud":
        return _set_cloud_consent(body)

    # 워크스페이스 범위
    scoped = _scoped(path)
    if scoped is not None:
        workspace_id, tail = scoped
        entry = _entry(state, workspace_id)
        out_dir = Path(entry.out_dir)
        if method == "GET":
            if tail == "dashboard":
                return 200, _dashboard(out_dir)
            if tail == "plan":
                return 200, _plan_payload(entry)
            if tail == "search":
                return _search(out_dir, query, state)
            if tail == "graph":
                return 200, _graph_payload(out_dir)
            if tail == "wiki":
                return 200, _wiki_tree(out_dir)
            if tail.startswith("wiki/"):
                return _wiki_page(out_dir, tail[len("wiki/") :])
        if method == "PUT" and tail == "options":
            # 스캔을 돌리지 않고도 모델을 저장할 수 있어야 한다. 그러지 않으면 «스캔이
            # 실패해서 옵션이 저장되지 않고 → 점검이 계속 기본 모델을 보고 → 무엇이
            # 잘못됐는지 알 수 없는» 순환에 갇힌다.
            #
            # **부분 갱신이다 — 보낸 키만 바꾸고 나머지는 남긴다.** 통째로 교체하면 설정
            # 화면에서 「모델 저장」을 누를 때 모델 두 개만 보내므로 `engine`·임계치 같은
            # 다른 저장값이 함께 지워진다. 드롭다운이 채워지기 전에 눌렀다면 설정이 통째로
            # 날아간다.
            merged = {**entry.last_options, **(body or {})}
            saved = workspaces.save_options(state.registry_path, workspace_id, merged)
            payload = asdict(saved)
            # 검색용 모델을 바꿨다면 **지금** 알려 준다. 미리 겁주는 문구 대신, 실제로
            # 그 일이 벌어진 시점에 무엇을 하면 되는지 화면이 버튼으로 준다.
            payload["index"] = _index_state(Path(saved.out_dir), saved.last_options)
            return 200, payload
        if method == "DELETE" and tail == "index":
            return _reset_index(out_dir)
        if method == "POST" and tail == "reveal":
            return _reveal(entry, body)
        if method == "PUT" and tail.startswith("wiki/"):
            return _save_wiki(out_dir, tail[len("wiki/") :], body, state)
    return 404, {"error": "없는 경로입니다."}


def _reveal(entry: workspaces.Workspace, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """원본이 있는 폴더를 파일 탐색기에서 연다.

    브라우저는 `http://` 페이지에서 `file://` 링크를 **조용히 무시한다** — 위키 본문의
    「원본 파일 열기」가 아무 반응도 없던 이유다. 브라우저가 못 하는 일이므로 서버가
    대신 연다.

    **파일을 실행하지는 않는다** (§4.11 의 «화면 요구로 위험을 들이지 않는다»). 요청 한
    번이 매크로가 든 통합문서나 실행 파일을 띄우는 통로가 되면 안 된다. 폴더를 열어 그
    파일을 골라 주고, 실제로 여는 것은 사용자가 한다.

    경로는 **이 워크스페이스 안**이어야 한다. 그러지 않으면 토큰을 쥔 쪽이 컴퓨터의 아무
    폴더나 열 수 있다.
    """
    raw = (body or {}).get("path")
    if not isinstance(raw, str) or not raw.strip():
        return 400, {"error": "경로가 필요합니다."}

    target = Path(raw)
    if not target.is_absolute():
        # 상대경로는 서버 프로세스의 cwd 기준으로 풀려 엉뚱한 폴더를 가리킨다 (§4.5).
        return 400, {"error": "절대경로만 받습니다."}
    target = target.resolve()

    roots = [Path(entry.source_dir).resolve(), Path(entry.out_dir).resolve()]
    if not any(target == root or target.is_relative_to(root) for root in roots):
        return 400, {"error": "이 워크스페이스 밖의 경로입니다."}

    folder = target if target.is_dir() else target.parent
    if not folder.is_dir():
        return 404, {"error": f"폴더가 없습니다: {folder}"}
    try:
        _open_in_file_manager(target if target.exists() else folder)
    except OSError as exc:
        return 400, {"error": f"폴더를 열지 못했습니다: {exc}"}
    # 원본이 사라졌어도 폴더는 열어 준다 — 「어디에 있던 문서인가」를 보여 주는 것이 목적이다.
    return 200, {"opened": str(folder), "selected": target.exists()}


def _open_in_file_manager(target: Path) -> None:
    """파일 탐색기로 `target` 을 보여 준다. 파일이면 **그 파일을 고른 채** 폴더를 연다.

    테스트는 이 함수를 대신 끼워 넣어(monkeypatch) 실제로 창이 뜨지 않게 한다.
    """
    if sys.platform == "win32":
        # **명령줄을 문자열로 넘긴다.** 인자 목록으로 주면 파이썬이 공백이 든 인자를 통째로
        # 감싸 `explorer "/select,D:\...\02. 가이드.docx"` 가 되는데, 탐색기는 그 형태를
        # 위치로 읽지 못하고 **조용히 기본 폴더(문서)를 연다** — 오류도 내지 않아 «폴더는
        # 열렸는데 엉뚱한 폴더»가 된다 [2026-09-02 실측]. 따옴표는 경로에만 둘러야 한다.
        #
        # 셸을 거치지 않는다(`shell=False`) — 이 문자열은 CreateProcess 에 그대로 간다.
        # Windows 경로에는 `"` 를 넣을 수 없으므로 따옴표를 벗어날 길이 없다.
        command = f'explorer /select,"{target}"' if target.is_file() else f'explorer "{target}"'
        # 탐색기는 성공해도 0 이 아닌 코드를 내는 일이 있어 반환을 기다리지 않는다.
        subprocess.Popen(command, close_fds=True)
        return

    if sys.platform == "darwin":
        args = ["open", "-R", str(target)] if target.is_file() else ["open", str(target)]
    else:
        args = ["xdg-open", str(target if target.is_dir() else target.parent)]
    # 셸을 거치지 않고 인자 목록으로 넘긴다 — 경로에 무엇이 들었든 명령으로 해석되지 않는다.
    subprocess.Popen(args, close_fds=True)


def _resolve_wiki(out_dir: Path, relative: str) -> Path:
    """`out_dir` 하위의 위키 파일 경로로 해석한다.

    **`out_dir` 밖으로 나가는 경로를 거절한다.** `..` 를 섞으면 서버가 임의의 파일을 읽어
    돌려주는 통로가 된다 — 이 서버는 로컬 파일시스템을 다루므로 그 자리가 실재한다.
    """
    candidate = (out_dir / relative).resolve()
    root = out_dir.resolve()
    if not candidate.is_relative_to(root):
        raise workspaces.WorkspaceStoreError("출력 폴더 밖의 경로입니다.")
    return candidate


#: 제목 한 줄을 찾기 위해 읽는 최대 바이트. 제목은 front-matter 바로 뒤에 오므로 이만큼이면
#: 충분하고, 문서가 많아도 파일 전체를 읽지 않는다 — 코어의 「통째로 메모리에 올리지 않는다」
#: 관행을 조회 경로에서도 지킨다.
_TITLE_PROBE_BYTES = 2048


def _wiki_title(path: Path) -> str:
    """위키의 `# 제목` 한 줄. 읽지 못하면 파일 이름으로 대신한다."""
    try:
        with path.open("r", encoding="utf-8") as stream:
            head = stream.read(_TITLE_PROBE_BYTES)
    except OSError:
        return path.name
    for line in head.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or path.name
    return path.name


def _wiki_tree(out_dir: Path) -> dict[str, Any]:
    """위키 목록 — `out_dir` 기준 상대경로와 **문서 제목** (§4.7).

    제목을 함께 주는 것은 화면이 목록을 «둘러보기»로 쓰기 때문이다. 파일 이름
    (`온보딩.md.md`)만 늘어놓으면 무엇이 들었는지 알 수 없다.
    """
    if not out_dir.is_dir():
        return {"entries": []}
    root = out_dir.resolve()
    entries = [
        {
            "path": str(p.relative_to(root)).replace("\\", "/"),
            "name": p.name,
            "title": _wiki_title(p),
        }
        for p in sorted(root.rglob(f"*{core.WIKI_SUFFIX}"))
        if p.is_file()
    ]
    return {"entries": entries}


def _wiki_page(out_dir: Path, relative: str) -> tuple[int, dict[str, Any]]:
    """위키 한 장 — **렌더된 HTML과 원문을 함께** 돌려준다 (§4.7).

    원문을 같이 주는 것은 편집 화면이 그것을 그대로 열기 때문이다. 화면이 HTML 을 다시
    마크다운으로 되돌리는 일은 없다.
    """
    target = _resolve_wiki(out_dir, relative)
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 404, {"error": f"그런 위키가 없습니다: {relative}"}
    except OSError as exc:
        return 400, {"error": f"위키를 읽지 못했습니다: {exc}"}

    document = markdown.split_front_matter(raw)
    return 200, {
        "path": relative,
        "title": _wiki_title(target),
        "front_matter": document.front_matter,
        "html": markdown.render(document.body),
        "raw": raw,
    }


def _save_wiki(
    out_dir: Path, relative: str, body: dict[str, Any], state: GuiState
) -> tuple[int, dict[str, Any]]:
    """편집 저장 (§4.9).

    두 가지를 막는다.

    1. **스캔 중 저장은 409.** 패스3의 마커 블록 갱신과 충돌해 한쪽이 덮인다 (§5).
    2. **마커가 사라졌으면 400** 이고 파일을 쓰지 않는다.
    """
    if state.jobs.running:
        return 409, {"error": "스캔이 도는 동안에는 위키를 저장할 수 없습니다."}

    text = body.get("raw")
    if not isinstance(text, str) or not text.strip():
        return 400, {"error": "본문이 비어 있습니다."}

    try:
        markdown.validate_editable(text)
    except markdown.MarkerMissingError as exc:
        return 400, {"error": str(exc)}

    target = _resolve_wiki(out_dir, relative)
    if not target.is_file():
        return 404, {"error": f"그런 위키가 없습니다: {relative}"}
    try:
        target.write_text(text, encoding="utf-8")
    except OSError as exc:
        return 400, {"error": f"위키를 저장하지 못했습니다: {exc}"}

    # **저장한 결과를 그대로 돌려준다** — 화면이 방금 쓴 내용을 바로 보여 줄 수 있어야 한다.
    # 화면이 스스로 렌더하게 하면 마크다운 렌더러가 두 벌이 되고, 그중 한쪽만 이스케이프를
    # 빠뜨리는 순간 §4.9 의 XSS 방어가 무너진다. 렌더는 서버 한 곳에만 둔다.
    status, page = _wiki_page(out_dir, relative)
    if status != 200:
        return 200, {"saved": True, "path": relative}
    page["saved"] = True
    return 200, page


def _scoped(path: str) -> tuple[str, str] | None:
    """`/api/workspaces/<id>/<tail>` 을 갈라낸다. 아니면 `None`."""
    prefix = "/api/workspaces/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    workspace_id, _, tail = rest.partition("/")
    return (workspace_id, tail) if tail else None


def _entry(state: GuiState, workspace_id: str) -> workspaces.Workspace:
    for entry in workspaces.load(state.registry_path):
        if entry.id == workspace_id:
            return entry
    raise workspaces.WorkspaceNotFoundError(f"그런 워크스페이스가 없습니다: {workspace_id}")


def _add_workspace(body: dict[str, Any], state: GuiState) -> tuple[int, dict[str, Any]]:
    name = str(body.get("name") or "").strip()
    source = str(body.get("source_dir") or "")
    out = str(body.get("out_dir") or "")
    if not name or not source or not out:
        return 400, {"error": "name·source_dir·out_dir 이 모두 필요합니다."}
    entry = workspaces.add(
        state.registry_path, name=name, source_dir=Path(source), out_dir=Path(out)
    )
    return 201, asdict(entry)


def _index_state(out_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
    """검색 데이터(벡터 인덱스)가 지금 설정과 맞는가.

    인덱스에는 **그것을 만든 임베딩 모델 이름**이 적혀 있고, 다른 모델의 벡터는 섞어 쓸 수
    없다. 코어는 이 경우 스캔을 막는데, 그 안내가 `--force` 같은 CLI 문구라 화면에 그대로
    내보내면 쓸모가 없다. 화면이 대신 판정해 «다시 만들기» 버튼을 준다.
    """
    from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

    path = index_path_for(out_dir)
    if not path.exists():
        return {"exists": False, "model": None, "rebuild_required": False}

    configured = resolve_embed_model(options.get("embed_model"))
    try:
        with SqliteVectorStore(path) as store:
            existing = store.model_name
    except sqlite3.Error:
        # 읽지 못하는 인덱스는 다시 만드는 것이 답이다.
        return {"exists": True, "model": None, "rebuild_required": True}
    return {
        "exists": True,
        "model": existing,
        "rebuild_required": existing is not None and existing != configured,
    }


def _reset_index(out_dir: Path) -> tuple[int, dict[str, Any]]:
    """검색 데이터를 지운다 — 다음 스캔이 새 모델로 다시 만든다.

    **위키와 그래프는 건드리지 않는다.** 지워지는 것은 벡터뿐이고, 원문이 그대로이므로
    다음 스캔에서 요약은 mtime 규칙으로 스킵된다(LLM 호출 0회).
    """
    from corpbrain.core.vectorstore import index_path_for

    path = index_path_for(out_dir)
    try:
        existed = path.exists()
        if existed:
            path.unlink()
    except OSError as exc:
        return 400, {"error": f"검색 데이터를 지우지 못했습니다: {exc}"}
    return 200, {"removed": existed}


def _dashboard(out_dir: Path) -> dict[str, Any]:
    """현황 — 위키 수 · 그래프 통계 · 마지막 스캔 (§4.7).

    **이력을 보관하지 않으므로**(§4.3.1) 추세를 담지 않는다. 없는 데이터를 그리지 않는다.
    """
    wiki_count = sum(1 for _ in out_dir.rglob(f"*{core.WIKI_SUFFIX}")) if out_dir.is_dir() else 0
    payload: dict[str, Any] = {
        "wiki_count": wiki_count,
        "last_run": runner.read_lastrun(out_dir),
        "graph": None,
    }
    graph_file = graph_path_for(out_dir)
    if graph_file.exists():
        with core.SqliteGraphStore(graph_file, read_only=True) as store:
            stats = store.stats()
        payload["graph"] = {
            "documents": stats.documents,
            "entities": stats.entities,
            "tags": stats.tags,
            "nodes": stats.nodes,
            "edges": stats.edges,
            "edges_by_type": dict(stats.edges_by_type),
        }
    return payload


def _plan_payload(entry: workspaces.Workspace) -> dict[str, Any]:
    """스캔 전 견적 (§4.7). LLM·네트워크 0이라 즉시 답한다."""
    options = {k: v for k, v in entry.last_options.items() if k in _PLAN_OPTIONS}
    plan = core.plan_scan(
        core.ScanConfig(folder=Path(entry.source_dir), out_dir=Path(entry.out_dir), **options)
    )
    return {
        "file_count": plan.file_count,
        "total_est_tokens": plan.total_est_tokens,
        "est_seconds": plan.est_seconds,
        "hardware": {"gpu": plan.hardware.gpu, "label": plan.hardware.label},
        "gate": None if plan.gate is None else asdict(plan.gate),
        "entries": [
            {
                "path": str(item.path),
                "ext": item.ext,
                "size_bytes": item.size_bytes,
                "est_tokens": item.est_tokens,
                "importance": item.importance,
            }
            for item in sorted(plan.entries, key=lambda e: -e.importance)[:20]
        ],
    }


#: `plan_scan` 이 실제로 보는 필드만 넘긴다 — 나머지는 견적에 영향이 없다.
_PLAN_OPTIONS = frozenset(
    {"max_chars", "max_file_size", "max_total_tokens", "max_files", "engine"}
)


def _search(out_dir: Path, query: dict[str, list[str]], state: GuiState) -> tuple[int, dict]:
    """검색 (§4.7). **스캔 중에는 409로 막는다** (§5).

    벡터 인덱스는 스캔이 쓰기 락을 실행 내내 점유하는데 `search` 는 조회인데도 인덱스를
    쓰기로 열어, 구조적으로 반드시 실패한다. UI 가 비활성화하더라도 타이밍 경합으로 요청이
    들어올 수 있으므로 여기서 한 번 더 막는다.
    """
    if state.jobs.running:
        return 409, {"error": "스캔이 도는 동안에는 검색할 수 없습니다."}
    text = _first(query.get("q")) or ""
    if not text.strip():
        return 400, {"error": "검색어가 필요합니다."}
    top_k = int(_first(query.get("top_k")) or 5)
    results = core.search_index(out_dir, text, top_k=top_k)
    return 200, {
        "results": [
            {
                "doc_id": item.doc_id,
                "score": item.score,
                "title": item.metadata.get("title") or item.doc_id,
                "source_path": item.metadata.get("source_path") or item.doc_id,
                "expansion": None if item.expansion is None else asdict(item.expansion),
            }
            for item in results
        ],
        "graph_used": graph_path_for(out_dir).exists(),
    }


def _graph_payload(out_dir: Path) -> dict[str, Any]:
    """그래프 전체 노드·엣지 (§4.7). `--max`(기본 50) 규모라 한 번에 돌려준다."""
    graph_file = graph_path_for(out_dir)
    if not graph_file.exists():
        return {"nodes": [], "edges": []}
    with core.SqliteGraphStore(graph_file, read_only=True) as store:
        ranking = store.degree_ranking()
        labels = store.nodes_of([doc_id for doc_id, _ in ranking])
        nodes = [
            {
                "id": doc_id,
                "type": "Document",
                "label": labels[doc_id].label if doc_id in labels else doc_id,
                "degree": degree,
            }
            for doc_id, degree in ranking
        ]
        edges = []
        for doc_id, _ in ranking:
            for edge in store.neighbors(doc_id):
                edges.append(
                    {"src": edge.src, "dst": edge.dst, "type": str(edge.type), "weight": edge.weight}
                )
    unique = {(e["src"], e["dst"], e["type"]): e for e in edges}
    return {"nodes": nodes, "edges": list(unique.values())}


def _installed_models(saved: dict[str, Any] | None = None) -> dict[str, Any]:
    """설치된 모델 목록과 **지금 실제로 쓰일 모델** (§4.7).

    화면이 자유 입력 대신 **고르게** 하기 위한 것이다. 오타로 없는 모델을 적어 스캔이
    실패하는 일이 사라진다.

    `resolved` 를 함께 준다 — 화면이 「기본값 사용」 같은 항목을 두더라도 **그것이 어떤
    모델인지 글자로 적을 수 있어야** 한다. 이름 없는 «기본값»은 사용자가 확인할 방법이 없다.

    **Ollama가 꺼져 있어도 오류로 만들지 않는다.** 목록이 비면 화면이 안내만 띄우면 되고,
    데몬이 없다는 사실은 바로 옆 환경 점검이 이미 말해 준다.
    """
    from corpbrain.core.llm.ollama_client import OllamaNotAvailableError, list_models

    options = saved or {}
    resolved = {
        "model": resolve_model(options.get("model")),
        "embed_model": resolve_embed_model(options.get("embed_model")),
        # 클라우드 엔진은 **다른 필드**(`cloud_model`)를 쓴다. 화면이 「이 엔진이 쓸 모델」을
        # 정직하게 적으려면 둘 다 알아야 한다 — 엔진이 클라우드일 때 Ollama 모델 이름을
        # 보여 주면 아무 효과 없는 값을 읽게 된다.
        "cloud_model": str(options.get("cloud_model") or core.DEFAULT_CLOUD_MODEL),
    }
    try:
        return {"models": list_models(), "available": True, "resolved": resolved}
    except OllamaNotAvailableError as exc:
        return {"models": [], "available": False, "detail": str(exc), "resolved": resolved}


def _doctor_payload(query: dict[str, list[str]], state: GuiState) -> dict[str, Any]:
    """환경 점검 (§4.7). 최악 7초가 걸릴 수 있다 — 화면이 스켈레톤을 보여 준다.

    **실제로 쓸 모델을 점검한다.** 인자 없이 `diagnose()` 를 부르면 코어 기본값
    (`qwen2.5:7b-instruct`·`qwen3-embedding:4b`)만 확인해, 다른 모델을 받아 둔 사용자에게
    「모델 없음」이라고 잘못 알린다. 모델이 없는 게 아니라 점검이 엉뚱한 것을 본 것이다.

    쓸 모델은 세 곳에서 온다 — 쿼리스트링 > 워크스페이스의 `last_options` > 환경변수 >
    코어 기본값. 앞의 둘이 «명시값»이고 나머지는 `resolve_model()` 이 처리한다.
    """
    explicit_model = _first(query.get("model"))
    explicit_embed = _first(query.get("embed_model"))

    workspace_id = _first(query.get("workspace_id"))
    if workspace_id:
        options = _entry(state, workspace_id).last_options
        explicit_model = explicit_model or options.get("model")
        explicit_embed = explicit_embed or options.get("embed_model")

    model = resolve_model(explicit_model)
    embed_model = resolve_embed_model(explicit_embed)
    report = core.diagnose(model=model, embed_model=embed_model)
    return {
        "ready": report.ready,
        "checks": _doctor_checks(report),
        # CLI와 같은 텍스트도 함께 둔다 — 사용자가 그대로 복사해 붙일 수 있고, 화면이
        # 못 다루는 항목이 생겨도 원본이 사라지지 않는다.
        "lines": build_doctor_lines(report),
        # 화면이 «무엇을 점검했는가»를 함께 보여 준다 — 이 값이 보이지 않으면 사용자가
        # 「모델 없음」을 자기 모델이 사라진 것으로 읽는다.
        "model": model,
        "embed_model": embed_model,
    }


#: 점검 항목의 상태. 화면이 색과 아이콘을 여기에 건다.
STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"


def _doctor_checks(report: core.DoctorReport) -> list[dict[str, Any]]:
    """`DoctorReport`를 화면이 그릴 수 있는 항목 목록으로 바꾼다.

    **CLI 문자열(`build_doctor_lines`)을 파싱하지 않는다.** 그렇게 하면 문구를 다듬을
    때마다 화면이 조용히 깨진다. 구조화된 필드에서 직접 만든다.

    `blocking` 은 **이것 때문에 스캔이 막히는가**다 — GPU 미탐지와 클라우드 미설정은
    경고일 뿐 `ready` 판정에 들어가지 않는다(v0.5 §3 항목10).
    """
    def check(
        status: str, label: str, detail: str = "", action: str = "", *, blocking: bool = False
    ) -> dict[str, Any]:
        return {
            "status": status,
            "label": label,
            "detail": detail,
            "action": action,
            "blocking": blocking,
        }

    checks = [
        check(
            STATUS_OK if report.installed else STATUS_FAIL,
            "Ollama 설치",
            "설치됨" if report.installed else "PATH에서 찾지 못함",
            "" if report.installed else "https://ollama.com 에서 설치하세요.",
            blocking=not report.installed,
        ),
        check(
            STATUS_OK if report.running else STATUS_FAIL,
            "Ollama 데몬",
            "구동 중" if report.running else "응답 없음",
            "" if report.running else "`ollama serve` 로 데몬을 띄우세요.",
            blocking=not report.running,
        ),
        check(
            STATUS_OK if report.model_present else STATUS_FAIL,
            "요약 모델",
            report.model,
            "" if report.model_present else f"`ollama pull {report.model}`",
            blocking=not report.model_present,
        ),
        check(
            STATUS_OK if report.embed_model_present else STATUS_FAIL,
            "임베딩 모델",
            report.embed_model,
            "" if report.embed_model_present else f"`ollama pull {report.embed_model}`",
            blocking=not report.embed_model_present,
        ),
        check(
            STATUS_OK if report.hardware.gpu else STATUS_WARN,
            "GPU 가속",
            report.hardware.label,
            "" if report.hardware.gpu else "CPU로 돌면 느립니다. 스캔에서 「게이트 무시」가 필요합니다.",
        ),
        check(
            STATUS_OK if report.cloud_ready else STATUS_WARN,
            "클라우드 엔진",
            "사용 가능" if report.cloud_ready else _cloud_missing(report),
            "" if report.cloud_ready else "로컬만 쓰신다면 그대로 두셔도 됩니다.",
        ),
    ]
    return checks


def _cloud_missing(report: core.DoctorReport) -> str:
    """클라우드가 준비되지 않은 **구체적 이유** — 둘 중 무엇이 빠졌는지 알려 준다."""
    missing = []
    if not report.cloud_consent:
        missing.append("동의 없음")
    if not report.cloud_api_key:
        missing.append(f"{API_KEY_ENV_VAR} 미설정")
    return " · ".join(missing)


def _cloud_settings() -> dict[str, Any]:
    from corpbrain.core.llm.anthropic_client import resolve_api_key

    try:
        has_key = bool(resolve_api_key())
    except Exception:  # noqa: BLE001 - 키가 없으면 그냥 없는 것이다
        has_key = False
    return {
        "granted": core.is_cloud_consent_granted(),
        "config_path": str(core.consent_path()),
        "api_key_env": API_KEY_ENV_VAR,
        "api_key_present": has_key,
        #: 동의 다이얼로그에 **반드시** 표시할 세 가지 (§4.10). 코어의
        #: `grant_cloud_consent()` 는 아무 고지도 하지 않고 파일만 쓴다.
        "notices": [
            "문서 내용이 외부(Anthropic)로 전송됩니다.",
            "주민등록번호 등 개인정보 7종은 전송 전에 자동 마스킹됩니다.",
            f"API 키는 {API_KEY_ENV_VAR} 환경변수로만 받으며 파일에 저장되지 않습니다.",
        ],
    }


def _set_cloud_consent(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    granted = bool(body.get("granted"))
    if granted:
        core.grant_cloud_consent()
    else:
        core.revoke_cloud_consent()
    return 200, _cloud_settings()


def _start_scan(body: dict[str, Any], state: GuiState) -> tuple[int, dict[str, Any]]:
    """스캔을 시작한다 (§4.7 `POST /api/scan`).

    옵션은 §4.7.1 대로 `ScanConfig` 필드를 그대로 받으며, 생략된 것은 코어 기본값이 된다 —
    서버가 값을 지어내지 않는다. 워크스페이스가 `folder`·`out_dir` 을 소유하므로 본문의
    그 두 값은 무시하고 레지스트리에서 채운다.
    """
    workspace_id = str(body.get("workspace_id") or "")
    entries = {entry.id: entry for entry in workspaces.load(state.registry_path)}
    entry = entries.get(workspace_id)
    if entry is None:
        return 404, {"error": f"그런 워크스페이스가 없습니다: {workspace_id}"}

    requested = {
        key: value
        for key, value in (body.get("options") or {}).items()
        if key not in {"folder", "out_dir"}
    }
    # **워크스페이스에 저장된 옵션을 밑에 깔고 요청이 덮는다.**
    #
    # 이것이 없으면 화면의 입력칸이 비어 있을 때 저장해 둔 모델이 무시되고 코어 기본값으로
    # 돌아 「받은 적 없는 모델을 찾지 못했다」로 실패한다. doctor 는 `last_options` 를 보는데
    # 스캔은 보지 않아, 막으려던 «점검은 통과했는데 실행은 다른 모델» 이 실제로 벌어졌다.
    options = {**entry.last_options, **requested}
    # 모델은 doctor 와 **같은 규칙**으로 해소한다 (명시값 > 환경변수 > 코어 기본값).
    # 그러지 않으면 「점검은 통과했는데 스캔은 다른 모델로 돌아 실패」가 된다.
    #
    # **해소한 값은 `payload` 에만 넣고 `options` 에는 넣지 않는다.** `options` 는 그대로
    # `last_options` 로 저장되는데, 거기에 해소 결과를 적으면 환경변수에서 온 값이 명시값으로
    # 굳어져 나중에 환경변수를 바꿔도 반영되지 않는다. 저장되는 것은 사용자가 실제로 입력한
    # 값뿐이어야 한다.
    payload = {
        **options,
        "model": resolve_model(options.get("model")),
        "embed_model": resolve_embed_model(options.get("embed_model")),
        "folder": entry.source_dir,
        "out_dir": entry.out_dir,
    }

    try:
        # 유효성은 러너가 쓰는 그 함수로 **미리** 검증한다 — 자식을 띄운 뒤 실패하면
        # 사용자에게는 「시작했다가 곧 죽었다」로 보인다.
        runner.config_from_payload(payload)
    except ValueError as exc:
        return 400, {"error": str(exc)}

    try:
        state.jobs.start(workspace_id=workspace_id, payload=payload)
    except scanjob.ScanAlreadyRunningError as exc:
        return 409, {"error": str(exc)}

    workspaces.save_options(state.registry_path, workspace_id, options)
    return 202, {"started": True, "workspace_id": workspace_id}


#: 정적 자산 폴더. `gui_preview/variants/minimalist`에서 **복사**해 온 것이 정본이며,
#: `gui_preview/`는 참고 자료로 그대로 남는다 (§4.8.1).
STATIC_DIR = Path(__file__).parent / "static"

#: 확장자 → Content-Type. **외부 자산이 없으므로 목록이 짧다** (§4.8.1 — CDN 제로).
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


def _content_type(name: str) -> str:
    return _CONTENT_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


def make_handler(state: GuiState, *, port: int | None = None) -> type[BaseHTTPRequestHandler]:
    """이 서버 인스턴스에 묶인 요청 핸들러 클래스를 만든다.

    `BaseHTTPRequestHandler` 는 요청마다 인스턴스를 새로 만들어 생성자 인자를 받을 수
    없으므로, 상태를 닫아 넣은 하위 클래스를 돌려준다.

    Args:
        state: 이 서버가 쥔 상태(토큰).
        port: `Host` 검증에 쓸 포트. `None`(기본)이면 **실제로 바인딩된 포트**를
            `self.server.server_address` 에서 읽는다 — `create_server(port=0)` 처럼 OS 가
            포트를 고르는 경우에도 검증이 어긋나지 않는다. 테스트만 이 값을 직접 준다.
    """

    class _Handler(BaseHTTPRequestHandler):
        server_version = "CorpBrain"
        sys_version = ""

        @property
        def _port(self) -> int:
            return port if port is not None else int(self.server.server_address[1])

        #: 기본 구현은 `sys.stderr` 에 매 요청을 찍는다. 서버 프로세스의 스트림을 어댑터가
        #: 소유하므로 조용히 둔다.
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PUT(self) -> None:
            self._dispatch("PUT")

        def do_DELETE(self) -> None:
            self._dispatch("DELETE")

        def _dispatch(self, method: str) -> None:
            split = urlsplit(self.path)
            query = parse_qs(split.query)
            # **퍼센트 인코딩을 되돌린다.** 브라우저는 한글·공백이 든 경로를 `%ED%95%98...`
            # 처럼 인코딩해 보내는데, 되돌리지 않으면 그 문자열 그대로를 파일명으로 찾아
            # 「그런 위키가 없습니다: %ED%95%98…」이 된다. `parse_qs` 는 쿼리를 알아서
            # 디코딩하므로 경로만 여기서 처리한다.
            #
            # 디코딩이 `..` 를 만들어 낼 수 있으나 경로 확인은 `_resolve_wiki`·`_send_static`
            # 이 **디코딩된 값으로** 하므로 탈출은 여전히 막힌다.
            path = unquote(split.path)
            failure = authorize(
                path=path,
                host=self.headers.get("Host"),
                header_token=self.headers.get(TOKEN_HEADER),
                query_token=_first(query.get(TOKEN_QUERY_KEY)),
                state=state,
                port=self._port,
            )
            if failure is not None:
                self._send_json(failure.status, {"error": failure.detail})
                return

            if method == "GET" and path in {"/", "/index.html"}:
                self._send_static("index.html")
                return
            if method == "GET" and path.startswith("/static/"):
                self._send_static(path[len("/static/") :])
                return

            try:
                status, payload = route(
                    method=method,
                    path=path,
                    query=query,
                    body=self._read_body(),
                    state=state,
                )
            except Exception as exc:  # noqa: BLE001 - 어떤 실패도 트레이스백으로 새지 않는다
                status, payload = 500, {"error": f"처리 중 오류가 발생했습니다: {exc}"}
            self._send_json(status, payload)

        def _read_body(self) -> dict[str, Any]:
            """요청 본문을 JSON 으로 읽는다. 본문이 없으면 빈 dict."""
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}

        def _send_static(self, name: str) -> None:
            """`corpbrain/gui/static/` 안의 파일만 낸다.

            **경로가 그 폴더 밖으로 나가면 거절한다** — `..` 를 섞어 임의 파일을 읽어 가는
            통로를 만들지 않는다.
            """
            try:
                target = (STATIC_DIR / name).resolve()
                target.relative_to(STATIC_DIR.resolve())
                body = target.read_bytes()
            except (ValueError, OSError):
                self._send_json(404, {"error": "없는 파일입니다."})
                return
            self._send_bytes(200, _content_type(target.name), body)

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(status, "application/json; charset=utf-8", body)

        def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # 이 응답을 다른 출처가 읽지 못하게 한다 — CORS 헤더를 내보내지 않는 것으로
            # 충분하지만, 임베드와 스니핑도 함께 막는다.
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def _first(values: list[str] | None) -> str | None:
    """`parse_qs` 결과에서 첫 값만 꺼낸다."""
    return values[0] if values else None


def create_server(
    state: GuiState,
    *,
    port: int = DEFAULT_PORT,
    attempts: int = PORT_ATTEMPTS,
) -> ThreadingHTTPServer:
    """`127.0.0.1`에 바인딩된 서버를 만든다. 포트가 사용 중이면 위로 한 칸씩 옮긴다.

    `port=0`을 주면 OS가 빈 포트를 고른다(테스트용).

    Args:
        state: 이 서버가 쥘 상태. 핸들러가 클래스 속성으로 참조한다.
        port: 시도할 첫 포트.
        attempts: 위로 몇 칸까지 더 시도하는가. `0`이면 첫 포트만 시도한다.

    Raises:
        PortUnavailableError: 범위 안에서 빈 포트를 찾지 못했다.
    """
    handler = make_handler(state)
    last: OSError | None = None
    for offset in range(attempts + 1):
        candidate = port + offset if port else 0
        try:
            return ThreadingHTTPServer((HOST, candidate), handler)
        except OSError as exc:
            last = exc
            continue
    raise PortUnavailableError(
        f"{HOST}:{port}부터 {attempts}칸까지 빈 포트를 찾지 못했습니다 — "
        "`--port`로 다른 포트를 지정하세요."
    ) from last


def entry_url(state: GuiState, *, port: int) -> str:
    """브라우저를 열 첫 진입 URL. 토큰을 쿼리스트링으로 싣는다 (§4.6.1).

    최초 요청에 커스텀 헤더를 붙일 방법이 없으므로 여기서만 URL을 쓴다. 페이지는 이 값을
    읽어 메모리에 두고 `history.replaceState()`로 주소창에서 지운다.
    """
    query = urlencode({TOKEN_QUERY_KEY: state.token})
    return f"http://{HOST}:{port}/?{query}"
