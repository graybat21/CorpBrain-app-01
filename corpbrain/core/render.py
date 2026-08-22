"""요약 JSON → 고정 마크다운 템플릿 결정적 렌더 (스펙 §4.4).

코드가 템플릿을 소유하므로 섹션 누락이 불가능하다 — 배열 필드가 비어도 헤더는 항상 남는다.
시각은 인자로 주입받아 동일 입력이 동일 출력을 내도록 한다(결정적 렌더).
"""

from __future__ import annotations

from collections.abc import Sequence
from posixpath import relpath

from corpbrain.core.config import ENGINE_LOCAL
from corpbrain.core.models import ReferenceDirection, RelatedDocument, SummaryResult

#: 생성물이 반드시 포함해야 하는 front-matter 키 (스펙 §3 완료의 정의 2번 · v0.5 §4.6 `engine`).
FRONT_MATTER_KEYS: tuple[str, ...] = (
    "source_path",
    "generated_at",
    "model",
    "engine",
    "source_bytes",
)

#: 생성물이 반드시 포함해야 하는 본문 섹션 헤더 (스펙 §4.4, 순서 고정).
SECTION_HEADERS: tuple[str, ...] = (
    "## 한 줄 요약",
    "## 핵심 포인트",
    "## 요약",
    "## 태그·키워드",
    "## 원문",
    "## 관련 문서",
)

#: 「관련 문서」를 감싸는 **기계 관리 마커** (v0.6 §4.5). 패스3은 이 사이만 교체하고, 마커가
#: 없으면 탐색하지 않고 파일 끝에 블록 전체를 추가한다.
#:
#: 헤딩(`## 관련 문서`)을 탐색해 자르는 방식을 쓰지 않는 이유는, 요약문 안에 그 문자열이
#: 들어간 문서(CorpBrain 자신이나 이 스펙을 스캔한 경우 실제로 발생한다)에서 뒤따르는
#: 「태그·키워드」·「원문」 섹션이 조용히 잘려 나가기 때문이다. `rerun.py`가 front-matter
#: 블록을 먼저 잘라내도록 고친 것과 같은 종류의 사고다.
RELATED_MARKER_START = "<!-- corpbrain:related:start -->"
RELATED_MARKER_END = "<!-- corpbrain:related:end -->"

#: 고립 문서의 「관련 문서」 본문 — 섹션을 생략하지 않는다 (v0.6 §4.5).
RELATED_EMPTY = "관련 문서 없음"


def render_markdown(
    summary: SummaryResult,
    source_path: str,
    model: str,
    source_bytes: int,
    generated_at: str,
    engine: str = ENGINE_LOCAL,
) -> str:
    """요약 결과를 스펙 §4.4 템플릿으로 렌더한다.

    Args:
        summary: LLM이 반환한 고정 필드 요약.
        source_path: 원문 절대경로 (front-matter와 `file://` 링크에 그대로 쓰인다).
        model: 요약에 사용한 모델 이름.
        source_bytes: 원문 바이트 크기.
        generated_at: ISO8601 생성 시각 (렌더러는 시각을 자체 생성하지 않는다).
        engine: 요약에 사용한 엔진 (`"local"`·`"cloud"`) — 생성물만 보고도 이 문서가
            외부로 나갔는지 구별할 수 있게 front-matter에 남긴다 (v0.5 §4.6).
    """
    lines: list[str] = [
        "---",
        f'source_path: "{_quote(source_path)}"',
        f'generated_at: "{_quote(generated_at)}"',
        f'model: "{_quote(model)}"',
        f'engine: "{_quote(engine)}"',
        f"source_bytes: {source_bytes}",
        "---",
        "",
        f"# {summary.title}",
        "",
        "## 한 줄 요약",
        summary.one_line_summary,
        "",
        "## 핵심 포인트",
        *[f"- {point}" for point in summary.key_points],
        "",
        "## 요약",
        summary.summary,
        "",
        "## 태그·키워드",
        ", ".join(summary.tags),
        "",
        "## 원문",
        f"[원본 파일 열기](file://{source_path})",
        "",
        # 렌더러가 빈 블록까지 소유한다 (v0.6 §4.5) — "코드가 템플릿을 소유하므로 섹션
        # 누락이 불가능하다"는 성질이 7번째 섹션까지 그대로 확장되고, 갓 생성된 위키에는
        # 마커가 항상 있어 패스3이 "없으면 추가" 경로를 탈 일이 없다.
        render_related_block([], relative_to=""),
        "",
    ]
    return "\n".join(lines)


def render_related_block(
    related: Sequence[RelatedDocument],
    *,
    relative_to: str,
    relative_paths: dict[str, str] | None = None,
) -> str:
    """「관련 문서」 마커 블록 전체를 렌더한다 (v0.6 §4.5).

    Args:
        related: 이미 §4.5 순위로 정렬·절단된 목록.
        relative_to: 이 블록이 들어갈 위키의 `--out` 기준 상대경로. 링크를 **그 파일 기준**
            상대경로로 만드는 데 쓴다 — 스펙 §4.5가 링크에 요구한 것은 "파일 탐색기·에디터에서
            그대로 동작"이고, `--out` 루트 기준 문자열을 그대로 쓰면 하위 폴더 문서의 링크가
            깨진다. 최상위 문서에서는 두 값이 같다.
        relative_paths: `doc_id` → `--out` 기준 위키 상대경로.
    """
    paths = relative_paths or {}
    body = [
        f"- [{item.title}]({_link(paths.get(item.doc_id, item.doc_id), relative_to)})"
        f"{_evidence(item)}"
        for item in related
    ]
    return "\n".join(
        [
            RELATED_MARKER_START,
            "## 관련 문서",
            *(body or [RELATED_EMPTY]),
            RELATED_MARKER_END,
        ]
    )


def replace_related_block(markdown: str, block: str) -> str:
    """마커 사이만 교체한다. 마커가 없으면 탐색하지 않고 파일 끝에 블록을 덧붙인다 (§4.5)."""
    start = markdown.find(RELATED_MARKER_START)
    end = markdown.find(RELATED_MARKER_END)
    if start == -1 or end == -1 or end < start:
        separator = "" if markdown.endswith("\n") else "\n"
        return f"{markdown}{separator}\n{block}\n"
    return markdown[:start] + block + markdown[end + len(RELATED_MARKER_END) :]


def _link(target: str, relative_to: str) -> str:
    """대상 위키로 가는, **이 파일 기준** 상대 링크."""
    if not relative_to:
        return target
    base = relative_to.rsplit("/", 1)[0] if "/" in relative_to else ""
    return relpath(target, base) if base else target


def _evidence(item: RelatedDocument) -> str:
    """왜 관련인지를 줄 끝에 붙인다 (§4.5)."""
    parts: list[str] = []
    if item.similarity is not None:
        parts.append(f"유사도 {item.similarity:.2f}")
    if item.reference is ReferenceDirection.MUTUAL:
        parts.append("서로 참조함")
    elif item.reference is ReferenceDirection.OUTGOING:
        parts.append("이 문서가 참조함")
    elif item.reference is ReferenceDirection.INCOMING:
        parts.append("이 문서를 참조함")
    if item.shared_tags:
        parts.append("공유 태그 " + " ".join(f"`{tag}`" for tag in item.shared_tags))
    if item.shared_entities:
        parts.append("공유 엔티티 " + " ".join(f"`{name}`" for name in item.shared_entities))
    return f" — {' · '.join(parts)}" if parts else ""


def _quote(value: str) -> str:
    """front-matter 큰따옴표 문자열에 안전하게 넣기 위해 백슬래시와 따옴표를 이스케이프한다."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
