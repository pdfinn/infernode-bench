# InferBench

A benchmark for LLMs writing **Inferno / InferNode** code.

InferBench measures whether a language model can produce working code in
the Inferno operating system's developer stack: **Limbo** authoring,
**Plan 9 idiom C**, **Inferno `sh`** (NOT Plan 9 `rc`), **9P-native
tool use** (the headline category — driving tools by `read`/`write`
against `/tool/*/ctl`, not via JSON tool calls), and **filesystem /
namespace concepts** (9P, `bind`, union directories, `ctl`/`data`/`status`
decomposition).

The benchmark is built on five primitives:

1. A **JSON-Schema-validated item format** (`schema/item.schema.json`) —
   every item declares its category, difficulty, prompt, grader, golden
   solution, and per-item SPDX provenance.
2. **Deterministic stratified subsets** (`subsets/{smoke,mini,full}.yaml`)
   resolved from the full item set by `(name, seed, item_set_hash)`,
   pinned so historical leaderboard rows stay comparable.
3. **Pluggable graders**: a compile-gate adapter that delegates to
   [`infernode-os-llm`](https://github.com/pdfinn/infernode-os-llm)'s
   native `limbo` / Inferno `sh` / `9c` validators; a trace-match
   grader for 9P tool use; an LLM-as-judge for open-ended fs_concepts;
   exact-match MCQ for closed-form fs_concepts.
4. A **runner CLI** (`python -m infernode_bench …`) that talks to any
   OpenAI-compatible chat completions endpoint.
5. A **datasheet, decontamination report, and per-item SPDX manifest**
   so the benchmark is citable and the provenance auditable.

## Status

**v0 scaffold.** The 50-item `baseline_v2` set from `infernode-os-llm`
has been migrated as the `smoke` subset. Goldens, per-category
expansion to ~800–1,400 items, decontamination, hold-out, and judge
validation are tracked under epic **IB-1** (see
`docs/INFERNODE-BENCH-EPIC.md` in the companion repo).

## Quick start

```sh
# install
pip install -e .[dev]

# list categories and item counts
python -m infernode_bench list

# resolve a subset deterministically (prints the chosen item IDs)
python -m infernode_bench subset resolve smoke

# validate every item against the schema
python -m infernode_bench validate

# run the smoke subset against a model
# (requires INFERNODE_OS_LLM env var pointing at a checkout of the
# companion repo so the compile-gate is reachable)
INFERNODE_OS_LLM=/path/to/infernode-os-llm \
    python -m infernode_bench run smoke \
        --model gpt-oss:20b \
        --base-url http://jetson.lan:11434/v1
```

## Categories

| Category          | Smoke | Current | Target (full) | Headline grader |
|-------------------|------:|--------:|--------------:|-----------------|
| `limbo_authoring` |  15   |   73    | ~400          | compile-gate (limbo) |
| `9p_tool_use`     |  15   |   63    | ~150          | trace-match     |
| `inferno_sh`      |   8   |   36    | ~120          | compile-gate (Inferno sh under emu) |
| `plan9_c`         |   6   |   33    | ~150          | compile-gate (`9c -c`) |
| `fs_concepts`     |   6   |   55    | ~250          | MCQ exact match + judge for open-ended |
| **Total**         | **49** | **260** | **~870**      |                 |

Plus 20 calibration items at `calibration/v0.yaml` (4 per category, IB-2).

## Layout

```
infernode-bench/
  schema/                  JSON Schema for items, subsets, results
  items/<category>/        per-item or per-cluster YAML records
  subsets/                 smoke / mini / full stratified subset specs
  infernode_bench/         the Python package: CLI, schema, subset,
                           graders, runners, decontamination
  docs/                    datasheet, methodology, decontamination
                           report, subsets, graders
  tests/                   schema validation + golden-passes-grader CI
  calibration/             Phase-0 calibration set (IB-2)
```

## License

Code: MIT (see `LICENSE`). Item content: per-item SPDX, see `NOTICE`.
