# InferBench runs — official records

One markdown file per benchmark run. **Each file is immutable** — once
committed it is the citable record of that exact measurement, pinned
to the bench code SHA and the InferNode compile-gate SHA that produced
it.

## How a record gets here

After a run completes:

```sh
python -m infernode_bench.leaderboard render-runs   # writes docs/runs/*.md
python -m infernode_bench.leaderboard render        # updates LEADERBOARD.md
```

The renderer reads `runs/*.jsonl` (which is `.gitignored` — those
files can be re-generated; their on-disk format may shift across
runner versions). It skips JSONLs whose modification time is within
the last 90 seconds (heuristic: still being written). For each
complete run it emits a fully-populated markdown report.

If methodology changes (new gate, new extractor, different runner
flags), the **previous record stays**. A fresh run produces a new
file with a new `run_id`. The leaderboard shows the lineage.

## What each record contains

* Identity pins — `run_id`, model, endpoint, subset (+hash), `bench_sha`,
  `infernode_sha`, timestamp.
* Configuration — max-token caps actually used, truncation count,
  endpoint protocol (`/v1` vs `/api`).
* Headline + per-category + per-difficulty + per-context-freshness
  pass-rate tables.
* Per-item verdict table (sorted by category) with elapsed time and a
  truncation marker (`⊘`).
* Up to five representative failure samples (one per category), each
  with gate stderr and a 400-char response snippet.
* Exact reproduction command.

## What it deliberately does NOT contain

* Model output bodies in full — those live in the JSONL artefact and
  are too large to track in git.
* Cost figures for API-billed runs — the runner records elapsed time
  but not dollar cost (the CLI shim returns `_x_cli_cost_usd` per call
  but it isn't propagated through InferBench's runner yet — TODO if it
  matters).

## Adding new runs

You don't manually write these files. Run the benchmark, then run the
renderer. The file you commit is what the renderer produced — don't
hand-edit (any edits will be clobbered on re-render, and the point of
the file is to be machine-generated from JSONL).
