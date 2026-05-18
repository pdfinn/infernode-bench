"""Leaderboard renderer (IB-23 scaffolding).

Walks `runs/*.jsonl` and emits `LEADERBOARD.md` with one row per
(model, subset_name, subset_hash, bench_sha, run_id). Per-row metrics:
overall pass rate + per-category pass rate + per-difficulty breakdown
+ run identity pins.

This is the publication surface: every row has the data needed to
reproduce.

Usage:
    python -m infernode_bench.leaderboard render
    python -m infernode_bench.leaderboard render --runs-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from infernode_bench.items import REPO_ROOT


def _load_run(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _aggregate(rows: list[dict]) -> dict:
    """One run = many item rows. Aggregate to a single-row summary."""
    if not rows:
        return {}
    head = rows[0]
    n_total = 0
    n_pass = 0
    n_truncated = 0
    by_cat: dict[str, list[int]] = defaultdict(list)
    by_diff: dict[str, list[int]] = defaultdict(list)
    by_fresh: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        ok = r.get("ok")
        if ok is None:
            continue  # skipped
        n_total += 1
        if ok:
            n_pass += 1
        if r.get("truncated"):
            n_truncated += 1
        cat = r.get("category", "?")
        diff = r.get("difficulty", "?")
        fresh = r.get("context_freshness", "cold")
        by_cat[cat].append(int(bool(ok)))
        by_diff[diff].append(int(bool(ok)))
        by_fresh[fresh].append(int(bool(ok)))
    rate = (100.0 * n_pass / n_total) if n_total else 0.0
    return {
        "model": head.get("model", "?"),
        "subset": head.get("subset_name", "?"),
        "subset_hash": (head.get("subset_hash") or "")[:12],
        "bench_sha": (head.get("bench_sha") or "")[:12],
        "infernode_sha": (
            (head.get("grader_detail", {}) or {}).get("infernode_sha") or ""
        )[:12],
        "run_id": head.get("run_id", "?"),
        "n_pass": n_pass,
        "n_total": n_total,
        "n_truncated": n_truncated,
        "pass_rate": rate,
        "by_category": {c: f"{sum(v)}/{len(v)}" for c, v in by_cat.items()},
        "by_difficulty": {d: f"{sum(v)}/{len(v)}"
                          for d, v in by_diff.items()},
        "by_freshness": {f: f"{sum(v)}/{len(v)}"
                         for f, v in by_fresh.items()},
    }


def render_markdown(summaries: list[dict]) -> str:
    if not summaries:
        return "# Leaderboard\n\n(no runs)\n"

    lines = [
        "# InferBench leaderboard",
        "",
        ("Auto-rendered from `runs/*.jsonl`. Each row pins the model, "
         "subset hash, bench SHA, and InferNode submodule SHA the gate "
         "used — historical rows stay comparable even as items/ grows."),
        "",
        "## Overall",
        "",
        ("| Run | Model | Subset | Pass | Rate | Trunc | Bench | Submodule |"),
        ("|-----|-------|--------|-----:|-----:|------:|-------|-----------|"),
    ]
    for s in summaries:
        lines.append(
            f"| `{s['run_id']}` "
            f"| `{s['model']}` "
            f"| {s['subset']} (`{s['subset_hash']}`) "
            f"| {s['n_pass']}/{s['n_total']} "
            f"| {s['pass_rate']:.1f}% "
            f"| {s.get('n_truncated', 0)} "
            f"| `{s['bench_sha']}` "
            f"| `{s['infernode_sha']}` |"
        )
    lines += ["", "## Per-category pass rate", ""]
    cats = sorted({c for s in summaries for c in s["by_category"]})
    header = "| Run | Model | " + " | ".join(cats) + " |"
    sep = "|" + ("---|" * (2 + len(cats)))
    lines.extend([header, sep])
    for s in summaries:
        row = [f"`{s['run_id']}`", f"`{s['model']}`"]
        for c in cats:
            row.append(s["by_category"].get(c, "—"))
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Per-difficulty pass rate", ""]
    diffs = ["trivial", "easy", "medium", "hard"]
    header = "| Run | Model | " + " | ".join(diffs) + " |"
    sep = "|" + ("---|" * (2 + len(diffs)))
    lines.extend([header, sep])
    for s in summaries:
        row = [f"`{s['run_id']}`", f"`{s['model']}`"]
        for d in diffs:
            row.append(s["by_difficulty"].get(d, "—"))
        lines.append("| " + " | ".join(row) + " |")
    # Per-freshness breakdown (IOL-38). Useful for separating cold-start
    # capability from primed/follow-on performance.
    freshness_levels = ["cold", "primed", "concept"]
    if any(s.get("by_freshness") for s in summaries):
        lines += ["", "## Per-context-freshness pass rate", ""]
        header = "| Run | Model | " + " | ".join(freshness_levels) + " |"
        sep = "|" + ("---|" * (2 + len(freshness_levels)))
        lines.extend([header, sep])
        for s in summaries:
            row = [f"`{s['run_id']}`", f"`{s['model']}`"]
            for f in freshness_levels:
                row.append(s.get("by_freshness", {}).get(f, "—"))
            lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines)


def render(args: argparse.Namespace) -> int:
    runs_dir = Path(args.runs_dir or REPO_ROOT / "runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in sorted(runs_dir.glob("*.jsonl")):
        rows = _load_run(path)
        if not rows:
            continue
        s = _aggregate(rows)
        if s:
            summaries.append(s)

    md = render_markdown(summaries)
    out = Path(args.output or REPO_ROOT / "LEADERBOARD.md")
    out.write_text(md)
    print(f"wrote {out}  ({len(summaries)} run(s))", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    pr = sub.add_parser("render")
    pr.add_argument("--runs-dir", default=None)
    pr.add_argument("--output", default=None)
    pr.set_defaults(func=render)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
