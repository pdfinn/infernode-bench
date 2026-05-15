# Graders

Four grader kinds; each takes `(item, model_response)` and returns a
`GradeResult` with `ok: bool`, optional `score`, and a grader-specific
`detail` dict.

## `compile_gate`

Delegates to `infernode-os-llm/tools/compile_gate/local.sh` (or its
Docker equivalent). Multi-language dispatch via `GATE_LANG`:

| Item language | `GATE_LANG` | Backend         |
|---------------|-------------|-----------------|
| `limbo`       | `limbo`     | Native `limbo` from the InferNode submodule, with `-I module/`. |
| `c`           | `c`         | plan9port `9c -c`. |
| `inferno_sh`  | `rc`        | Inferno `sh` under headless `emu`, parse-only with `load std`. |

The bench repo does NOT duplicate the gate — it shells out. Two backends:

- **subprocess (default).** Set `INFERNODE_OS_LLM` to a checkout path.
  Fast, no Docker, requires that the checkout has been bootstrapped
  (`make bootstrap-limbo` once).
- **docker.** Set `INFERBENCH_GATE_BACKEND=docker`. Image defaults to
  `infernode-os-llm/compile-gate:latest`; override with
  `INFERBENCH_GATE_IMAGE`. IOL is on the hook for publishing tagged
  images to `ghcr.io` (linked ticket).

Result `detail`:

```jsonc
{
  "gate_lang": "limbo",
  "backend": "local",                  // local | docker | timeout | broken
  "dis_size": 1284,                    // .dis output size; None on fail
  "wrapped": false,                    // gate prepended `implement Snippet;`
  "stderr_tail": "…",                  // last 500 chars on fail
  "infernode_sha": "abc123…",          // InferNode submodule SHA
  "code_chars": 412
}
```

Cited in leaderboard rows so historical comparisons stay honest:
`bench_sha` + `subset_hash` + `infernode_sha` + grader version.

## `trace_match`

For `9p_tool_use`. The model's response is parsed into a 9P op trace
(write/read against `/tool/<name>/{ctl,doc,…}`) and compared to the
item's golden trace. The trace extractor prefers a fenced JSON block
tagged ` ```trace ` or ` ```json `; falls back to a static scan of
`read(...)`, `write(...)`, etc. against `/tool/*` paths.

Distance is Levenshtein on the sequence of `(op, path, data)`
triples. Items declare `max_edit_distance` (default 0); equivalence
classes are applied to both sides before scoring.

v0 equivalence classes (more to come, IB-8b):

- `drop_redundant_read` — adjacent reads of the same path collapse.
- `reorder_writes` — adjacent writes to distinct paths may be reordered.

For a production-grade implementation that records the *actual* op
trace the model's code would emit if executed, see IB-8a (in-process
Veltro tool mock).

## `mcq`

Closed-form fs_concepts. Each item declares `config.choices: [A, B, …]`
and `golden.answer: "B"`. The extractor handles common output shapes:

```
B
(B)
**B**
Answer: B
Final answer: **C**
After thinking I think B is correct.
```

Strategy: first look for an explicit `answer is`/`Answer:` cue;
otherwise pick the first standalone letter in the valid range.

## `judge`

Open-ended fs_concepts. Each item declares:

- `config.criteria: [list of named criteria]`
- `config.judge_model: "gpt-5.1"` (optional; env override available)
- `golden.exemplar: "…"` (for calibration; the grader does NOT reward
  similarity to it)

The judge is queried via the same OpenAI-compatible endpoint shape the
runner uses (set `INFERBENCH_JUDGE_BASE_URL` and either
`INFERBENCH_JUDGE_MODEL` or per-item override). The judge prompt
template is committed (`infernode_bench/graders/judge.py`) and
versioned via `JUDGE_PROMPT_VERSION`; changing the prompt requires a
re-run for compatibility.

Validation: IB-17 — 50-item human-vs-judge sample, target κ ≥ 0.6 per
criterion. Items below threshold are tightened or converted to MCQ.

## Failure modes the graders explicitly handle

| Failure                       | Surfaced by                                   |
|-------------------------------|-----------------------------------------------|
| Model emits no code           | `compile_gate.detail.reason = "no code extracted"` |
| Gate runner crashed           | `compile_gate.detail.backend = "broken"`      |
| Plan 9 rc syntax in Inferno sh| Gate's `RC_BUILTIN_USAGE_RE` catches the usage line; result `ok=false`. |
| Model wrote to `/tool/x/body` | `trace_match` distance against a `/tool/x/ctl` golden grows; bench-side `decontamination/anti_patterns.py` (TBD) will eventually surface it as a known-bogus tool subfile. |
| Judge non-JSON reply          | `judge.detail.reason = "judge reply was not JSON"`; row marked failure. |
| Item with `needs_golden: true`| Runner skips by default; `--include-needs-golden` to opt in. |
