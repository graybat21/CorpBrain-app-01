"""워크스페이스 레지스트리 — `~/.corpbrain/workspaces.json` (v0.9 스펙 §4.5).

**GUI만 아는 저장소다.** 코어와 CLI는 워크스페이스 개념을 모르며, 이 슬라이스는 코어에
워크스페이스 모듈을 두지 않는다(스펙 §2 비목표). 필요해지면 후속 버전에서 승격한다.

경로는 **언제나 절대경로로 저장·전달한다.** 브라우저가 보낸 `./inbox`는 서버 프로세스의
cwd 기준으로 풀려 사용자가 의도하지 않은 폴더를 가리키므로, 저장 시점에 한 번 확정한다.

쓰기는 `corpbrain/core/consent.py`의 관용구를 계승해 **원자적**이다 — 같은 디렉터리의 임시
파일에 쓰고 `os.fsync` 후 `os.replace`로 교체하므로 쓰기 도중 중단돼도 깨진 JSON이 남지
않는다.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from corpbrain.core.consent import default_config_path
from corpbrain.core.errors import PreconditionError

__all__ = [
    "REGISTRY_FILENAME",
    "VOLATILE_OPTIONS",
    "DirectoryListing",
    "Workspace",
    "WorkspaceNotFoundError",
    "WorkspaceStoreError",
    "add",
    "default_registry_path",
    "list_directories",
    "load",
    "remove",
    "save_options",
]

#: 동의 파일과 같은 폴더에 둔다 — 설정이 한 곳에 모인다.
REGISTRY_FILENAME = "workspaces.json"

#: **저장하지 않는 실행 옵션** (grill T6).
#:
#: 둘 다 「이번 한 번만」의 성격이라 조용히 유지되면 놀란다 — 어제 켠 `force`가 오늘도
#: 켜져 있으면 전체 재요약이 돌아 LLM 비용이 예기치 않게 발생하고, `force_gates`는 막으라고
#: 둔 게이트를 계속 무력화한다. 매번 꺼진 채로 시작한다.
VOLATILE_OPTIONS = frozenset({"force", "force_gates"})


class WorkspaceStoreError(PreconditionError):
    """레지스트리를 읽거나 쓰지 못했다 — 어댑터가 오류로 매핑한다."""


class WorkspaceNotFoundError(WorkspaceStoreError):
    """그 `id`를 가진 워크스페이스가 목록에 없다."""


@dataclass(frozen=True)
class Workspace:
    """워크스페이스 하나 (§4.5).

    `source_dir`·`out_dir`은 **절대경로 문자열**이다. `Path`가 아니라 문자열로 두는 것은
    이 값이 그대로 JSON이 되고 그대로 API 응답이 되기 때문이다.
    """

    id: str
    name: str
    source_dir: str
    out_dir: str
    created_at: str
    #: 마지막 스캔에 쓴 실행 옵션. `VOLATILE_OPTIONS`는 담기지 않는다.
    last_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectoryListing:
    """폴더 탐색 결과 (§4.7).

    브라우저는 로컬 경로를 서버에 줄 수 없다 — `<input type="file" webkitdirectory>`는
    파일을 업로드할 뿐 경로를 주지 않는다. 그래서 서버가 목록을 돌려주고 사용자가 화면에서
    폴더를 고른다.
    """

    #: 지금 보고 있는 폴더의 절대경로.
    path: str
    #: 상위 폴더의 절대경로. 루트에서는 `None`이다.
    parent: str | None
    #: 하위 폴더들. 파일은 담지 않는다.
    entries: list[Path]


def default_registry_path() -> Path:
    """`~/.corpbrain/workspaces.json`. 동의 파일과 같은 폴더다."""
    return default_config_path().parent / REGISTRY_FILENAME


def load(registry_path: Path) -> list[Workspace]:
    """레지스트리를 읽는다. 파일이 없으면 빈 목록이다.

    **손상된 파일을 빈 목록으로 보지 않는다.** 그렇게 하면 다음 쓰기가 사용자의 목록을
    통째로 덮어써 조용히 지운다. 동의 파일이 읽기 실패를 「동의 없음」으로 수렴시키는 것과
    방향이 다른데, 거기서는 판정 불가가 **거부**로 기울어야 안전하기 때문이다.

    Raises:
        WorkspaceStoreError: 파일이 있으나 JSON이 아니거나 모양이 다르다.
    """
    try:
        raw = registry_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise WorkspaceStoreError(
            f"워크스페이스 목록을 읽지 못했습니다: {registry_path} ({exc})"
        ) from exc

    try:
        document = json.loads(raw)
        items = document["workspaces"]
        return [
            Workspace(
                id=item["id"],
                name=item["name"],
                source_dir=item["source_dir"],
                out_dir=item["out_dir"],
                created_at=item["created_at"],
                last_options=dict(item.get("last_options") or {}),
            )
            for item in items
        ]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise WorkspaceStoreError(
            f"워크스페이스 목록이 손상됐습니다: {registry_path} ({exc}) — "
            "내용을 확인하거나 파일을 지우고 다시 등록하세요."
        ) from exc


def add(registry_path: Path, *, name: str, source_dir: Path, out_dir: Path) -> Workspace:
    """워크스페이스를 등록하고 저장한다.

    이름은 표시용이라 겹쳐도 된다 — 식별은 `id`가 한다.
    """
    entry = Workspace(
        id=uuid.uuid4().hex,
        name=name,
        source_dir=_absolute(source_dir),
        out_dir=_absolute(out_dir),
        created_at=datetime.now(UTC).isoformat(),
    )
    _write(registry_path, [*load(registry_path), entry])
    return entry


def remove(registry_path: Path, workspace_id: str) -> None:
    """목록에서 지운다. **위키·인덱스 파일은 건드리지 않는다** (§4.7)."""
    entries = load(registry_path)
    remaining = [entry for entry in entries if entry.id != workspace_id]
    if len(remaining) == len(entries):
        raise WorkspaceNotFoundError(f"그런 워크스페이스가 없습니다: {workspace_id}")
    _write(registry_path, remaining)


def save_options(registry_path: Path, workspace_id: str, options: dict[str, Any]) -> Workspace:
    """마지막 실행 옵션을 기록한다 — `VOLATILE_OPTIONS`는 걸러낸다 (grill T6)."""
    entries = load(registry_path)
    kept = {key: value for key, value in options.items() if key not in VOLATILE_OPTIONS}
    updated: Workspace | None = None
    result: list[Workspace] = []
    for entry in entries:
        if entry.id == workspace_id:
            updated = Workspace(
                id=entry.id,
                name=entry.name,
                source_dir=entry.source_dir,
                out_dir=entry.out_dir,
                created_at=entry.created_at,
                last_options=kept,
            )
            result.append(updated)
        else:
            result.append(entry)
    if updated is None:
        raise WorkspaceNotFoundError(f"그런 워크스페이스가 없습니다: {workspace_id}")
    _write(registry_path, result)
    return updated


def list_directories(path: Path) -> DirectoryListing:
    """`path` 아래의 **하위 폴더만** 돌려준다 (§4.7).

    읽을 수 없는 항목은 조용히 건너뛴다 — 폴더를 고르는 화면이 권한 하나 때문에 통째로
    실패하면 안 된다.

    Raises:
        WorkspaceStoreError: 경로가 없거나 폴더가 아니다.
    """
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise WorkspaceStoreError(f"폴더가 아닙니다: {resolved}")

    entries: list[Path] = []
    try:
        for child in resolved.iterdir():
            try:
                if child.is_dir():
                    entries.append(child)
            except OSError:
                continue
    except OSError as exc:
        raise WorkspaceStoreError(f"폴더를 읽지 못했습니다: {resolved} ({exc})") from exc

    parent = resolved.parent
    return DirectoryListing(
        path=str(resolved),
        parent=None if parent == resolved else str(parent),
        entries=sorted(entries, key=lambda p: p.name),
    )


def _absolute(path: Path) -> str:
    """상대경로를 절대경로 문자열로 확정한다 (§4.5).

    폴더가 아직 없어도 된다 — `out_dir`은 첫 스캔이 만든다. 그래서 `resolve(strict=False)`다.
    """
    return str(path.expanduser().resolve())


def _write(registry_path: Path, entries: list[Workspace]) -> None:
    """원자적으로 교체한다 — `consent.py`의 쓰기 관용구를 그대로 계승한다."""
    document = {"version": 1, "workspaces": [asdict(entry) for entry in entries]}
    body = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            dir=registry_path.parent, prefix=f".{registry_path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, registry_path)
        except BaseException:
            # 교체에 실패했으면 임시 파일을 남기지 않는다.
            with suppress(OSError):
                os.unlink(temp_name)
            raise
    except OSError as exc:
        raise WorkspaceStoreError(
            f"워크스페이스 목록을 저장하지 못했습니다: {registry_path} ({exc})"
        ) from exc
