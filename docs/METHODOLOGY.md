# InferBench methodology

This document describes how InferBench measures what it claims to
measure. Decisions here are intentionally conservative — we prefer
sharper readings on narrower claims to broader claims with murkier
grading.

## What the benchmark measures

**Whether a language model can produce *working* code in the Inferno
operating system's developer stack.** "Working" means one of:

| Category          | "Working" means                                                                                      |
|-------------------|------------------------------------------------------------------------------------------------------|
| `limbo_authoring` | The model's output compiles via the InferNode native `limbo` compiler with `-I module/`.            |
| `plan9_c`         | The model's output compiles via plan9port `9c -c`.                                                  |
| `inferno_sh`      | The model's output parses cleanly under Inferno `sh` (under `emu -c1 .../sh.dis`), not Plan 9 `rc`. |
| `9p_tool_use`     | The model's 9P op trace (read/write against `/tool/<name>/{ctl,doc}`) matches the golden trace, modulo declared equivalence classes. |
| `fs_concepts`     | MCQ items: exact-match on the letter. Open-ended items: LLM-as-judge against per-item rubric + exemplar; κ ≥ 0.6 vs human. |

What the benchmark explicitly does NOT measure: code style, comment
quality, "looks Plan-9-y" aesthetics, doc-string compliance,
performance, security. It measures *compiles-clean / matches-trace /
answers-correctly* — these are necessary, not sufficient.

## North-star metric

A single number per (model, category) pair, with a 95% bootstrap CI.
Reported categories are the five above; the **headline category is
`9p_tool_use`** because the operating-system-level deliverable being
benchmarked is 9P-native tool calling. Per-difficulty splits are
reported as a secondary signal.

## Subsets

Three subsets:

| Subset | Items   | Use                                                                |
|--------|--------:|--------------------------------------------------------------------|
| smoke  |  ~50    | Quick sanity check. One-to-one with IOL's baseline_v2.             |
| mini   | ~150    | Default published number — small enough to run cheap, large enough for CIs. |
| full   | ~800–1400 | All public items. Use for the published leaderboard rows.        |

Subsets are *deterministic stratified samples* of the underlying item
set. The resolver mixes the subset seed with each (category,
sub-skill) bucket so independent strata don't share shuffles. The
resolved item-id list is hashed (sha256); the hash is recorded in
every result row so changes to the underlying item set are detectable
against historical rows.

## Hold-out

20% of every category, stratified by sub-skill and difficulty, lives
in a separate **private** repo (`pdfinn/infernode-bench-private`) and
is never published. If a model scores materially higher on the
public set than on the hold-out, public contamination is implied.
See `docs/HOLDOUT-POLICY.md` (IB-19).

## Graders

See `docs/GRADERS.md`.

## Decontamination

See `docs/DECONTAMINATION.md`. Briefly: every item is checked for
n-gram overlap against (a) upstream Vita Nuova / Lucent `inferno-os`,
(b) the InferNode tree itself, (c) plan9port, (d) the Inferno
Programmer's Manual. Items with ≥3 unique 13-grams matching a source
are transformed or dropped.

## What we do *not* claim

- We do not claim that compile-pass-rate implies *correctness*. The
  compile gate validates syntax + type-shape; it does not run the
  program. A program can compile and behave incorrectly. We treat
  compile-pass-rate as a *strong necessary signal*: a model that
  cannot produce compiling Limbo cannot author Limbo.
- We do not claim that a high `9p_tool_use` score implies the model
  understands 9P generally. The grader compares against expected
  traces in the **Veltro tool surface** specifically.
- We do not claim that the LLM-as-judge for `fs_concepts` is
  human-equivalent. We claim only that it agrees with the author on a
  validated 50-item sample at κ ≥ 0.6.

## Versioning policy

- Items are versioned via their ID suffix (`_v1`, `_v2`, …).
  Mutating an item in-place is forbidden; bump the version, leave the
  predecessor in place with `deprecated: true`, and let the resolver
  exclude deprecated items by default.
- Graders are versioned via the grader prompt's `*_VERSION` constant
  (e.g. `JUDGE_PROMPT_VERSION`); changing the prompt forces a leaderboard
  re-run.
- Subset specs themselves can change, but the `resolved_hash` in every
  leaderboard row pins what was *actually* sampled.
