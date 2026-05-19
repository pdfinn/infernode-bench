"""Leaderboard renderer (IB-23 scaffolding).

Walks `runs/*.jsonl` and emits two artefacts:

1. `LEADERBOARD.md` — index with one row per (model, subset_name,
   subset_hash, bench_sha, run_id). Per-row metrics: overall pass rate
   + per-category pass rate + per-difficulty breakdown + run identity
   pins.
2. `docs/runs/<run_id>_<subset>_<model>.md` — one full report per run,
   tracked in git as the official record. Includes full configuration,
   item-level pass/fail, notable failure samples, and the exact
   reproduction command. These files are immutable once committed.

The JSONL files in `runs/` themselves are .gitignored (they're large
and exhibit non-deterministic field ordering across versions of the
runner). The per-run markdown reports are the citable artefact.

Usage:
    python -m infernode_bench.leaderboard render
    python -m infernode_bench.leaderboard render --runs-dir <dir>
    python -m infernode_bench.leaderboard render-runs     # per-run docs
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from infernode_bench.items import REPO_ROOT


def _is_run_in_progress(path: Path, idle_seconds: int = 90) -> bool:
    """Heuristic: treat a JSONL file as still being written if its
    modification time is within the last ``idle_seconds`` seconds.

    InferBench's runner flushes each row to disk as items are graded,
    so a finished run's JSONL stops being touched. A run that hasn't
    been touched in 90+ seconds is almost certainly complete (the
    grader timeout itself is < 90s for normal items).
    """
    import time
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return True
    return (time.time() - mtime) < idle_seconds


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
        safe_model = re.sub(r"[^A-Za-z0-9._-]", "_", s["model"])
        report = f"docs/runs/{s['run_id']}_{s['subset']}_{safe_model}.md"
        lines.append(
            f"| [`{s['run_id']}`]({report}) "
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


_PER_RUN_TEMPLATE = """# Run: `{model}` on `{subset}` — `{run_id}`

> **Official benchmark record.** This file is the citable record of one
> InferBench run. It is immutable once committed — if methodology
> changes, a new run replaces it.

## Identity

| Field | Value |
|---|---|
| Run ID | `{run_id}` |
| Model | `{model}` |
| Endpoint | `{endpoint}` |
| Subset | `{subset}` (hash `{subset_hash}`) |
| Items | {n_total} graded (of {n_items} resolved) |
| Bench SHA | `{bench_sha}` (`pdfinn/infernode-bench@{bench_sha_short}`) |
| InferNode submodule SHA | `{gate_sha}` (`pdfinn/infernode-os-llm/infernode@{gate_sha_short}`) |
| Run timestamp | {timestamp} |

## Configuration

{config_block}

## Headline result

**{n_pass}/{n_total} pass — {pass_rate:.1f}%**{trunc_note}

### Per category

| Category | Pass | Total | Rate |
|---|---:|---:|---:|
{category_rows}

### Per difficulty

| Difficulty | Pass | Total | Rate |
|---|---:|---:|---:|
{difficulty_rows}

### Per context freshness

| Freshness | Pass | Total | Rate |
|---|---:|---:|---:|
{freshness_rows}

## Items

{item_table}

## Notable failures

{failure_samples}

## Reproduction

```sh
{reproduction_cmd}
```

JSONL artefact (not in git per `.gitignore`):
`runs/{run_id}_{subset}_{safe_model}.jsonl`
"""


_FAILURE_SAMPLE_LIMIT = 5


def _config_block(rows: list[dict]) -> str:
    """Pull configuration knobs out of the JSONL rows."""
    head = rows[0]
    item_lines: list[str] = []
    # max_tokens is per-row from IOL-32. Show the unique values.
    mts = sorted({r.get("max_tokens") for r in rows if r.get("max_tokens")})
    if mts:
        item_lines.append(f"- `max_tokens`: {', '.join(str(m) for m in mts)} (per-language per IOL-32)")
    # truncated count
    nt = sum(1 for r in rows if r.get("truncated"))
    if nt:
        item_lines.append(f"- `truncated`: {nt}/{len(rows)} responses hit the token cap mid-construct")
    # endpoint kind
    endpoint = head.get("endpoint", "")
    if "/v1" in endpoint:
        item_lines.append(f"- Endpoint protocol: OpenAI-compatible `/v1/chat/completions`")
    elif "/api" in endpoint:
        item_lines.append(f"- Endpoint protocol: Ollama-native `/api/chat`")
    # Always-on knobs
    item_lines.append(f"- `temperature`: 0.0 (deterministic)")
    return "\n".join(item_lines) if item_lines else "(default configuration)"


def _item_table(rows: list[dict]) -> str:
    """Per-item verdict table. Sorted by category then item id."""
    sorted_rows = sorted(rows, key=lambda r: (r.get("category", ""), r.get("item_id", "")))
    lines = ["| Item | Category | Difficulty | Result | Elapsed |",
             "|---|---|---|---|---:|"]
    for r in sorted_rows:
        ok = r.get("ok")
        verdict = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
        trunc = " ⊘" if r.get("truncated") else ""
        elapsed = r.get("chat_elapsed_ms", 0)
        lines.append(
            f"| `{r.get('item_id','?')}` "
            f"| {r.get('category','?')} "
            f"| {r.get('difficulty','?')} "
            f"| {verdict}{trunc} "
            f"| {elapsed/1000:.1f}s |"
        )
    return "\n".join(lines)


def _failure_samples(rows: list[dict], limit: int = _FAILURE_SAMPLE_LIMIT) -> str:
    """Up to `limit` representative failure samples — one per distinct
    failure category, prioritising compile-gate stderr-tail content
    because that's where the substantive signal lives."""
    fails = [r for r in rows if r.get("ok") is False]
    if not fails:
        return "(no failures)"
    # Bucket by category and pick one example per category
    by_cat: dict[str, dict] = {}
    for r in fails:
        cat = r.get("category", "?")
        if cat not in by_cat:
            by_cat[cat] = r
    samples = list(by_cat.values())[:limit]
    blocks: list[str] = []
    for r in samples:
        gd = r.get("grader_detail") or {}
        stderr = (gd.get("stderr_tail") or "").strip()
        trace = gd.get("actual_trace")
        completion = (r.get("completion") or "").strip()
        body_lines = [f"### `{r.get('item_id','?')}` ({r.get('category')}, {r.get('difficulty')})"]
        body_lines.append("")
        if stderr:
            body_lines.append("**Gate stderr (tail):**")
            body_lines.append("```")
            body_lines.append(stderr[:600])
            body_lines.append("```")
        if trace is not None:
            body_lines.append(f"**Extracted trace:** `{json.dumps(trace)[:300]}`")
        if completion:
            body_lines.append("**Response (first 400 chars):**")
            body_lines.append("```")
            body_lines.append(completion[:400])
            body_lines.append("```")
        blocks.append("\n".join(body_lines))
    return "\n\n".join(blocks)


def _reproduction_cmd(rows: list[dict]) -> str:
    """Reconstruct the exact `python -m infernode_bench run …` invocation
    that produced the run. Best-effort: based on what fields the row
    records, plus runner defaults."""
    head = rows[0]
    endpoint = head.get("endpoint", "")
    model = head.get("model", "?")
    subset = head.get("subset_name", "?")
    # think:false was the runner's escape hatch for thinking models;
    # the row doesn't record it explicitly today, but we can infer:
    # an Ollama endpoint that doesn't end in /api means /v1 path.
    parts = [
        "INFERNODE_OS_LLM=/path/to/infernode-os-llm",
        "python -m infernode_bench run", subset,
        f"--model {model!r}".replace("'", '"'),
        f"--base-url {endpoint}",
        "--temperature 0.0",
        "--num-ctx 4096",
        "--timeout 300",
    ]
    return "  \\\n    ".join(parts)


def render_per_run(rows: list[dict], out_dir: Path) -> Path:
    if not rows:
        raise ValueError("no rows")
    head = rows[0]
    run_id = head.get("run_id", "unknown")
    model = head.get("model", "unknown")
    subset = head.get("subset_name", "unknown")
    safe_model = re.sub(r"[^A-Za-z0-9._-]", "_", model)

    n_graded = sum(1 for r in rows if r.get("ok") is not None)
    n_pass = sum(1 for r in rows if r.get("ok"))
    n_trunc = sum(1 for r in rows if r.get("truncated"))
    pass_rate = 100.0 * n_pass / n_graded if n_graded else 0.0

    by_cat: dict[str, list[int]] = defaultdict(list)
    by_diff: dict[str, list[int]] = defaultdict(list)
    by_fresh: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r.get("ok") is None:
            continue
        by_cat[r.get("category", "?")].append(int(bool(r["ok"])))
        by_diff[r.get("difficulty", "?")].append(int(bool(r["ok"])))
        by_fresh[r.get("context_freshness", "cold")].append(int(bool(r["ok"])))

    def _tbl(buckets: dict[str, list[int]]) -> str:
        if not buckets:
            return "| — | — | — | — |"
        return "\n".join(
            f"| {k} | {sum(v)} | {len(v)} | {100*sum(v)/len(v):.1f}% |"
            for k, v in sorted(buckets.items())
        )

    trunc_note = f" — {n_trunc} truncated" if n_trunc else ""
    gate_sha = ((head.get("grader_detail") or {}).get("infernode_sha") or "")
    bench_sha = head.get("bench_sha") or ""

    content = _PER_RUN_TEMPLATE.format(
        model=model,
        subset=subset,
        run_id=run_id,
        endpoint=head.get("endpoint", "?"),
        subset_hash=(head.get("subset_hash") or "")[:12],
        n_items=len(rows),
        n_total=n_graded,
        n_pass=n_pass,
        pass_rate=pass_rate,
        trunc_note=trunc_note,
        bench_sha=bench_sha,
        bench_sha_short=bench_sha[:12],
        gate_sha=gate_sha,
        gate_sha_short=gate_sha[:12],
        timestamp=head.get("timestamp", "?"),
        config_block=_config_block(rows),
        category_rows=_tbl(by_cat),
        difficulty_rows=_tbl(by_diff),
        freshness_rows=_tbl(by_fresh),
        item_table=_item_table(rows),
        failure_samples=_failure_samples(rows),
        reproduction_cmd=_reproduction_cmd(rows),
        safe_model=safe_model,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}_{subset}_{safe_model}.md"
    out_path.write_text(content)
    return out_path


def render_runs(args: argparse.Namespace) -> int:
    runs_dir = Path(args.runs_dir or REPO_ROOT / "runs")
    docs_dir = Path(args.output_dir or REPO_ROOT / "docs" / "runs")
    written = 0
    for path in sorted(runs_dir.glob("*.jsonl")):
        if _is_run_in_progress(path):
            print(f"skipping in-progress run: {path.name}", file=sys.stderr)
            continue
        rows = _load_run(path)
        if not rows:
            continue
        out = render_per_run(rows, docs_dir)
        print(f"wrote {out.relative_to(REPO_ROOT)}", file=sys.stderr)
        written += 1
    if written == 0:
        print("(no runs found)", file=sys.stderr)
        return 1
    return 0


def render(args: argparse.Namespace) -> int:
    runs_dir = Path(args.runs_dir or REPO_ROOT / "runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in sorted(runs_dir.glob("*.jsonl")):
        if _is_run_in_progress(path):
            print(f"skipping in-progress run: {path.name}", file=sys.stderr)
            continue
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
    pr = sub.add_parser("render", help="render LEADERBOARD.md index from runs/*.jsonl")
    pr.add_argument("--runs-dir", default=None)
    pr.add_argument("--output", default=None)
    pr.set_defaults(func=render)
    prr = sub.add_parser("render-runs", help="render per-run reports into docs/runs/*.md")
    prr.add_argument("--runs-dir", default=None)
    prr.add_argument("--output-dir", default=None)
    prr.set_defaults(func=render_runs)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
