"""docs/smoke/embedding_reassessment.py 의 순수 로직 단위 테스트.

이 스크립트는 corpbrain 패키지가 아니라 docs/smoke/ 하위의 일회성 개발자 도구라
importlib로 파일 경로를 직접 로드한다. 실제 Ollama 호출(embed_text)은 여기서
검증하지 않는다 — 스크립트는 사용자가 로컬에서 실행한다(스펙 §4.4).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "docs" / "smoke" / "embedding_reassessment.py"
_CORPUS_PATH = Path(__file__).resolve().parents[2] / "docs" / "smoke" / "corpus"


def _load_module():
    spec = importlib.util.spec_from_file_location("embedding_reassessment", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def er():
    return _load_module()


def test_nearest_neighbor_finds_highest_cosine_excluding_self(er):
    vectors = {
        "a": [1.0, 0.0],
        "b": [0.9, 0.1],
        "c": [0.0, 1.0],
    }
    assert er.nearest_neighbor("a", vectors) == "b"


def test_nearest_neighbor_returns_none_when_alone(er):
    assert er.nearest_neighbor("a", {"a": [1.0, 0.0]}) is None


def test_pairwise_matrix_has_no_duplicates_or_self_pairs(er):
    vectors = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [1.0, 1.0]}
    rows = er.pairwise_matrix(vectors)
    pairs = {(a, b) for a, b, _score in rows}
    assert len(rows) == 3
    assert ("a", "a") not in pairs
    assert pairs == {("a", "b"), ("a", "c"), ("b", "c")}


def test_top1_hit_rate_counts_hits_against_ground_truth(er, monkeypatch):
    monkeypatch.setattr(
        er,
        "GROUND_TRUTH",
        {
            "인사/채용계획.md": {"인사/온보딩.md"},
            "인사/온보딩.md": {"인사/채용계획.md"},
            # 실제 1위 이웃은 온보딩(코사인 0.828)이지만 정답은 채용계획으로 걸어 둬 미스를 만든다.
            "기타/무관.md": {"인사/채용계획.md"},
        },
    )
    vectors = {
        "인사/채용계획.md": [1.0, 0.0],
        "인사/온보딩.md": [0.9, 0.436],
        "기타/무관.md": [0.5, 0.866],
    }
    rate, hits = er.top1_hit_rate(vectors)
    assert hits["인사/채용계획.md"] is True
    assert hits["인사/온보딩.md"] is True
    assert hits["기타/무관.md"] is False
    assert rate == pytest.approx(2 / 3)


def test_top1_hit_rate_excludes_isolated_docs_not_in_ground_truth(er, monkeypatch):
    monkeypatch.setattr(er, "GROUND_TRUTH", {"a": {"b"}, "b": {"a"}})
    vectors = {"a": [1.0, 0.0], "b": [0.9, 0.1], "isolated": [0.0, 1.0]}
    _rate, hits = er.top1_hit_rate(vectors)
    assert "isolated" not in hits


def test_load_corpus_normalizes_posix_separators(er, tmp_path):
    (tmp_path / "폴더").mkdir()
    (tmp_path / "폴더" / "문서.md").write_text("본문", encoding="utf-8")
    docs = er.load_corpus(tmp_path)
    assert docs == {"폴더/문서.md": "본문"}


def test_check_ground_truth_matches_corpus_reports_both_directions(er):
    doc_ids = set(er.GROUND_TRUTH) | er.ISOLATED_DOCS
    doc_ids.add("유령/문서.md")  # 코퍼스에는 있다고 가정하되 매핑엔 없는 케이스
    doc_ids.discard(next(iter(er.ISOLATED_DOCS)))  # 매핑엔 있는데 코퍼스엔 없는 케이스

    problems = er.check_ground_truth_matches_corpus(doc_ids)

    assert any("코퍼스에 없는 문서" in p for p in problems)
    assert any("코퍼스에는 있지만" in p for p in problems)


def test_ground_truth_matches_actual_repo_corpus(er):
    """docs/smoke/corpus/ 의 실제 파일 목록과 GROUND_TRUTH·ISOLATED_DOCS 가 정확히 일치한다.

    코퍼스에 문서를 추가·삭제하면서 GROUND_TRUTH 갱신을 깜빡하는 것을 여기서 잡는다.
    """
    docs = er.load_corpus(_CORPUS_PATH)
    problems = er.check_ground_truth_matches_corpus(set(docs))
    assert problems == []


def test_corpus_has_24_docs_6_folders_2_isolated(er):
    docs = er.load_corpus(_CORPUS_PATH)
    folders = {doc_id.split("/")[0] for doc_id in docs}
    assert len(docs) == 24
    assert len(folders) == 6
    assert len(er.ISOLATED_DOCS) == 2
    assert er.ISOLATED_DOCS.issubset(docs.keys())
