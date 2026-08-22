"""증분 재실행 정책 — 원문 mtime이 기존 위키보다 최신일 때만 재생성 (스펙 §4.2).

요약·렌더 이전 단계에서 평가해 변경 없는 파일에 대한 불필요한 LLM 호출을 막는다.
재생성하지 않는 파일은 실패가 아니라 `SkipReason.UP_TO_DATE`로 보고된다 (FR-015·FR-016).

v0.5부터는 mtime에 더해 **엔진 전환**도 재생성 사유다 — 기존 위키가 어느 엔진으로
만들어졌는지는 front-matter `engine` 값에 남아 있고, 이번 실행의 `--engine`과 다르면
mtime과 무관하게 다시 만든다 (v0.5 스펙 §4.6). 사용자가 엔진을 바꾼 의도가 즉시 반영된다.
"""

from __future__ import annotations

import re
from pathlib import Path

from corpbrain.core.config import ENGINE_LOCAL

#: front-matter 블록 — 파일 맨 앞의 `---` 부터 다음 `---` 까지.
#: **본문까지 뒤지지 않기 위해** 블록을 먼저 잘라낸다. 본문에는 요약문이 그대로 들어가는데,
#: 그 문단이 우연히 `engine:` 으로 시작하면(설정 파일을 요약한 문서 등) 그 줄을 기록된
#: 엔진으로 잘못 읽어 재생성 판정이 어긋난다.
_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\s*$", re.DOTALL | re.MULTILINE)

#: front-matter 안의 `engine: "..."` 한 줄. 값의 따옴표는 있어도 없어도 읽는다.
_ENGINE_LINE = re.compile(r'^engine:\s*"?([^"\r\n]*?)"?\s*$', re.MULTILINE)

#: front-matter 안의 `source_path: "..."` 한 줄 (v0.6). 위키에서 원문 `doc_id`를 되찾는다.
_SOURCE_PATH_LINE = re.compile(r'^source_path:\s*"?([^"\r\n]*?)"?\s*$', re.MULTILINE)

#: front-matter를 찾기 위해 읽어들이는 앞부분 크기(바이트). 템플릿상 front-matter는
#: 200바이트 안팎이라 넉넉하며, 위키 전체를 메모리에 올리지 않기 위한 상한이다.
_FRONT_MATTER_PEEK = 2048


def should_regenerate(
    source_path: Path,
    out_path: Path,
    force: bool = False,
    engine: str | None = None,
) -> bool:
    """원문을 다시 요약·렌더해야 하는지 판단한다.

    Args:
        source_path: 원문 파일 경로.
        out_path: FR-012 미러링 규칙으로 산정한 위키 경로.
        force: `--force` — mtime과 무관하게 강제 재생성.
        engine: 이번 실행의 요약 엔진(선택). 주면 기존 위키의 front-matter `engine` 값과
            비교해 다를 때 mtime과 무관하게 재생성한다 (v0.5 §4.6). `None`이면 엔진을
            보지 않는다(v0.4까지의 동작).

    Returns:
        재생성해야 하면 True, 최신 상태라 건너뛰어도 되면 False.
    """
    if force:
        return True
    if not out_path.exists():
        return True
    # 값싼 판정(stat 두 번)을 먼저 본다 — 어차피 재생성이면 위키를 열어 읽을 이유가 없다.
    # 두 조건은 OR이라 순서를 바꿔도 결과가 같고, 로컬 경로에서는 사실상 매번 mtime만으로
    # 결론이 난다(엔진이 늘 `local`이므로). 50개 파일 재스캔에서 파일 열기 50번을 아낀다.
    if source_path.stat().st_mtime > out_path.stat().st_mtime:
        return True
    return engine is not None and read_engine(out_path) != engine


def read_engine(out_path: Path) -> str:
    """기존 위키 front-matter에 기록된 엔진을 읽는다 (v0.5 §4.6).

    `engine` 키가 없는 위키(v0.4 이전 생성물)는 `"local"`로 본다 — 클라우드 경로가
    존재하지 않던 시절의 산출물은 정의상 로컬이며, 이렇게 해야 v0.5로 올린 것만으로
    기존 위키가 전부 재생성되지 않는다(로드맵의 하위 호환 불변식).

    읽기에 실패하면(권한·인코딩 등) 역시 `"local"`로 본다 — 판정 실패가 대량 재생성으로
    번지지 않게 하고, 실제 재생성 여부는 뒤이은 mtime 비교가 결정하게 둔다.
    """
    try:
        with out_path.open("r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(_FRONT_MATTER_PEEK)
    except OSError:
        return ENGINE_LOCAL
    block = _FRONT_MATTER.search(head)
    if block is None:
        return ENGINE_LOCAL  # front-matter가 없거나 잘렸다 — 본문은 보지 않는다
    match = _ENGINE_LINE.search(block.group(1))
    if match is None:
        return ENGINE_LOCAL
    return match.group(1).strip() or ENGINE_LOCAL


def read_source_path(out_path: Path) -> str:
    """기존 위키 front-matter에 기록된 원문 절대경로를 읽는다 (v0.6 §4.1 노드 ID 체계).

    그래프의 대상은 이번 실행에서 처리한 문서가 아니라 `--out`에 존재하는 **위키 전체**이므로
    (v0.6 §4.1), 디스크의 위키에서 `doc_id`를 되찾을 수단이 필요하다. 위키 폴더만 복사해 온
    경우처럼 이번 스캔 대상에 없는 문서도 이 값으로 그래프에 참여한다.

    읽기에 실패하거나 키가 없으면 빈 문자열을 돌려준다 — 그 위키는 그래프에서 조용히 빠진다.
    """
    try:
        with out_path.open("r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(_FRONT_MATTER_PEEK)
    except OSError:
        return ""
    block = _FRONT_MATTER.search(head)
    if block is None:
        return ""
    match = _SOURCE_PATH_LINE.search(block.group(1))
    return match.group(1).strip() if match else ""
