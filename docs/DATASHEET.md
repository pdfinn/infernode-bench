# Datasheet for InferBench v0

Following Gebru et al., *Datasheets for Datasets* (2021).
**v0 status:** scaffold complete; sections marked TBD will be filled
during release prep (IB-21).

## 1. Motivation

**For what purpose was this dataset created?** To measure whether a
language model can produce working code in the Inferno operating
system's developer stack (Limbo, Plan 9 idiom C, Inferno `sh`,
9P-native tool use, filesystem / namespace concepts). The headline
deliverable is **9P-native tool calling**: driving Veltro tools by
reading and writing `/tool/*/ctl` files, not via JSON tool-call
shims.

**Who created the dataset?** The maintainers of `pdfinn/infernode-bench`.

**Funding.** Self-funded.

## 2. Composition

**What do the instances represent?** Programming or conceptual tasks
about the Inferno OS, paired with a grader that judges whether a
model's response is correct.

**How many instances are there?** v0: 50 (the migrated baseline_v2 set
from `infernode-os-llm`). Target for v1: ~800–1,400 across the five
categories. TBD: actual counts at v1 release.

**Per-instance fields.** See `schema/item.schema.json`. Briefly: `id`,
`category`, `difficulty`, `prompt`, `language`, `grader`, `golden`,
`provenance` (with SPDX), `tags`, `notes`.

**Splits.** A 20% hold-out per category lives in a private repo
(`pdfinn/infernode-bench-private`). The remaining 80% is public.

## 3. Collection process

**How were the items collected?** Hand-authored, optionally
LLM-assisted with human review and gate validation. The v0 migrated set
was authored by hand for `infernode-os-llm`'s eval pipeline. Per-item
`provenance.authored_by ∈ {human, llm-assisted, synth}` records the
collection mode.

**Sampling strategy.** Stratified by category and sub-skill. Targets
declared in `docs/INFERNODE-BENCH-EPIC.md` (companion IOL repo).

## 4. Preprocessing / cleaning / labeling

**Goldens.** Every non-deprecated item has a `golden` field that
passes its declared grader. CI enforces this (`make verify-items`).

**Decontamination.** See `docs/DECONTAMINATION.md`.

## 5. Uses

**Tasks the dataset is suitable for.** Benchmarking LLMs on Inferno OS
code authoring, 9P tool driving, and filesystem-conceptual knowledge.

**Tasks the dataset is NOT suitable for.** General-purpose code
benchmarks, performance benchmarking, security benchmarking,
multilingual or non-Inferno OS work.

## 6. Distribution

**How is the dataset distributed?** Public Git repository:
`https://github.com/pdfinn/infernode-bench`. The hold-out set is
private (`infernode-bench-private`).

**License.** Code: MIT. Item content: per-item SPDX (see `NOTICE` and
each item's `provenance.spdx`).

## 7. Maintenance

**Maintainers.** TBD.

**Update cadence.** TBD. Anticipated: quarterly minor updates to add
items; annual major bump to refresh the hold-out (25% rotated public,
replaced by fresh items).

**Errata / item retirement.** Items found to be ambiguous, broken, or
contaminated are deprecated (`deprecated: true`) — not deleted. The
resolver excludes them by default; historical leaderboard rows that
included them remain comparable via the recorded `subset_hash`.
