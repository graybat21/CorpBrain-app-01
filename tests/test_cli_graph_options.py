"""`scan`의 v0.6 그래프 옵션 배선 (v0.6 스펙 §4.7)."""

from __future__ import annotations

from pathlib import Path

from corpbrain import cli
from corpbrain.core import DEFAULT_RELATED_TOP_K, DEFAULT_SIMILARITY_THRESHOLD


def _config(argv: list[str]):
    args = cli.build_parser().parse_args(argv)
    return cli.build_config(args)


def test_defaults_preserve_backward_compatibility(tmp_path: Path) -> None:
    """신규 파라미터는 선택이고 기본값이 보존된다 (ROADMAP §5 하위 호환 불변식)."""
    config = _config(["scan", str(tmp_path)])

    assert config.similarity_threshold == DEFAULT_SIMILARITY_THRESHOLD
    assert config.related_top_k == DEFAULT_RELATED_TOP_K


def test_options_are_passed_through_to_the_core(tmp_path: Path) -> None:
    config = _config(
        ["scan", str(tmp_path), "--similarity-threshold", "0.85", "--related-top-k", "3"]
    )

    assert config.similarity_threshold == 0.85
    assert config.related_top_k == 3
