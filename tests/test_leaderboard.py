"""Leaderboard renderer — aggregation logic."""

from infernode_bench.leaderboard import _aggregate, render_markdown


def test_aggregate_basic():
    rows = [
        {"model": "m", "subset_name": "smoke", "subset_hash": "h" * 32,
         "bench_sha": "b" * 40, "run_id": "r1",
         "category": "limbo_authoring", "difficulty": "easy", "ok": True},
        {"model": "m", "subset_name": "smoke", "subset_hash": "h" * 32,
         "bench_sha": "b" * 40, "run_id": "r1",
         "category": "limbo_authoring", "difficulty": "hard", "ok": False},
        {"model": "m", "subset_name": "smoke", "subset_hash": "h" * 32,
         "bench_sha": "b" * 40, "run_id": "r1",
         "category": "9p_tool_use", "difficulty": "easy", "ok": True},
    ]
    s = _aggregate(rows)
    assert s["n_pass"] == 2 and s["n_total"] == 3
    assert s["pass_rate"] > 60 and s["pass_rate"] < 70
    assert s["by_category"]["limbo_authoring"] == "1/2"


def test_aggregate_skips_none_ok():
    rows = [
        {"model": "m", "ok": None, "category": "fs_concepts",
         "difficulty": "easy"},
        {"model": "m", "ok": True, "category": "fs_concepts",
         "difficulty": "easy"},
    ]
    s = _aggregate(rows)
    assert s["n_total"] == 1


def test_render_markdown_handles_empty():
    md = render_markdown([])
    assert "(no runs)" in md


def test_render_markdown_includes_columns():
    rows = [
        {"model": "m", "subset_name": "smoke", "subset_hash": "h" * 32,
         "bench_sha": "b" * 40, "run_id": "r1",
         "category": "limbo_authoring", "difficulty": "easy", "ok": True},
    ]
    md = render_markdown([_aggregate(rows)])
    assert "limbo_authoring" in md
    assert "smoke" in md
    assert "Per-category pass rate" in md
