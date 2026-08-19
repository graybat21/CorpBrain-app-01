"""임베딩 입력 텍스트 조립 — 위키 요약 콘텐츠에서 청크 분할 없이 문서당 1개 텍스트를 뽑는다
(v0.4 스펙 §4.3: "문서당 벡터 1개", 입력은 렌더링된 위키의 요약 콘텐츠).
"""

from __future__ import annotations

from corpbrain.core.models import SummaryResult


def summary_embedding_text(summary: SummaryResult) -> str:
    """신선하게 생성된 `SummaryResult`에서 임베딩 입력 텍스트를 만든다."""
    parts = [
        summary.title,
        summary.one_line_summary,
        *summary.key_points,
        summary.summary,
        *summary.tags,
    ]
    return "\n".join(part for part in parts if part)


def parse_wiki_markdown(markdown: str) -> tuple[str, str]:
    """이미 기록된 위키 마크다운에서 (제목, 임베딩 입력 텍스트)를 뽑는다.

    재실행 시 위키 재생성은 스킵되지만 인덱스에 벡터가 없는 문서를 백필할 때 쓴다 —
    `SummaryResult`가 없으므로 저장된 파일에서 직접 복원한다(v0.4 스펙 §4.3 증분 규칙).
    """
    body = _strip_front_matter(markdown).strip()
    title = ""
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return title, body


def _strip_front_matter(markdown: str) -> str:
    """앞의 `---...---` front-matter 블록을 제거한다(경로·시각 등 임베딩에 무의미한 메타데이터)."""
    if not markdown.startswith("---"):
        return markdown
    end = markdown.find("\n---", 3)
    if end == -1:
        return markdown
    return markdown[end + len("\n---") :]
