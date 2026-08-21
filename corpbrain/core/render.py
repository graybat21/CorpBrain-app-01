"""요약 JSON → 고정 마크다운 템플릿 결정적 렌더 (스펙 §4.4).

코드가 템플릿을 소유하므로 섹션 누락이 불가능하다 — 배열 필드가 비어도 헤더는 항상 남는다.
시각은 인자로 주입받아 동일 입력이 동일 출력을 내도록 한다(결정적 렌더).
"""

from __future__ import annotations

from corpbrain.core.config import ENGINE_LOCAL
from corpbrain.core.models import SummaryResult

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
)


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
    ]
    return "\n".join(lines)


def _quote(value: str) -> str:
    """front-matter 큰따옴표 문자열에 안전하게 넣기 위해 백슬래시와 따옴표를 이스케이프한다."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
