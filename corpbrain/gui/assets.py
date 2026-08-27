"""정적 자산 탐색 — `importlib.resources` (v0.9 스펙 §4.10.1).

자산은 **파이썬 패키지 안**(`corpbrain/gui/static/`)에 둔다. hatchling의
`packages = ["corpbrain"]` 설정이 그대로 자산까지 거두므로 빌드 설정 특례가 필요 없고,
**`-e` 개발 설치와 wheel 설치가 같은 코드 경로**를 쓴다.

설치 위치를 계산하거나 `__file__` 상대 경로를 조립하지 않는다 — 저장소 루트에 두고
`force-include`로 끌어오는 방식은 경로 해석이 두 설치 형태에서 갈려 분기가 생긴다.
"""

from __future__ import annotations

from importlib import resources

__all__ = ["ASSET_CONTENT_TYPES", "AssetNotFound", "content_type_for", "read_asset"]

#: 자산이 사는 패키지.
_PACKAGE = "corpbrain.gui.static"

#: 확장자 → Content-Type. `mimetypes`를 쓰지 않는 이유는 그 매핑이 OS 레지스트리에
#: 의존해 환경마다 갈리기 때문이다 — 특히 Windows에서 `.js`가 `text/plain`으로 나와
#: 브라우저가 스크립트를 거부하는 사고가 흔하다. 우리가 내는 자산은 몇 종뿐이다.
ASSET_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


class AssetNotFound(LookupError):
    """요청한 자산이 패키지에 없다 — 404로 매핑된다."""


def content_type_for(name: str) -> str:
    """파일 이름의 확장자로 Content-Type을 정한다. 모르는 확장자는 옥텟 스트림."""
    _, _, suffix = name.rpartition(".")
    return ASSET_CONTENT_TYPES.get(f".{suffix}", "application/octet-stream")


def read_asset(name: str) -> bytes:
    """자산 하나를 바이트로 읽는다.

    `name`은 `static/` 아래의 **단일 파일 이름**이다. 하위 디렉터리와 `..`를 허용하지
    않는다 — 경로 조립을 하지 않으므로 트래버설이 원천적으로 성립하지 않는다.

    Raises:
        AssetNotFound: 이름이 형식에 맞지 않거나 그런 자산이 없는 경우.
    """
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise AssetNotFound(name)
    try:
        return (resources.files(_PACKAGE) / name).read_bytes()
    except (FileNotFoundError, OSError, ModuleNotFoundError) as exc:
        raise AssetNotFound(name) from exc
