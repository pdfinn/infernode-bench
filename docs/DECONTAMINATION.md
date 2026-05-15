# Decontamination

**Status: stub.** The full n-gram pipeline is tracked under IB-18.

## Goal

Every item in `items/**` must satisfy: either the item is *not* present
in any of the listed corpora, or it is present, the fact is documented
in `provenance.derived_from`, and the item is licensed appropriately.

## Corpora the audit covers

| Corpus                              | Risk    | Notes                                                              |
|-------------------------------------|---------|--------------------------------------------------------------------|
| Upstream Vita Nuova `inferno-os`    | High    | Public Bitbucket repo, indexed, almost certainly in Common Crawl.  |
| InferNode tree (`infernode-os/infernode`) | High | Pinned-SHA submodule of IOL; potentially overlapping Limbo items.  |
| Plan 9 from User Space (`9fans/plan9port`) | Medium | Source of truth for Plan 9 idiom C items.                          |
| Inferno Programmer's Manual (Vita Nuova LaTeX) | Medium | Authoritative reference for `fs_concepts` MCQ — phrasings must be original. |

## Method (planned, IB-18)

For each item:

1. Tokenise `prompt` and (when present) `golden.source` / `golden.exemplar`.
2. Compute the set of k-grams (k=13).
3. For each corpus, compute the set of k-grams in the corpus body.
4. Flag the item if **≥3 unique k-grams** from the item appear in the
   corpus.

Triage outcomes:

- *Transformed.* Rename identifiers, recompose structure, replace
  example data. Re-check.
- *Dropped.* Removed from `items/**`.
- *Documented.* Item legitimately derives from upstream; SPDX is set,
  `provenance.derived_from` records the path, and the leaderboard
  publishes a per-category contamination percentage.

## Per-item provenance

Every item carries a `provenance` block:

```yaml
provenance:
  authored_by: human            # human | llm-assisted | synth
  contributor: "<github>"       # optional
  derived_from: null            # path in upstream tree if applicable
  spdx: "MIT"                   # SPDX license identifier
  source_repo: "infernode-os-llm@<sha>"   # optional pre-migration home
```

The CI pipeline emits `LICENSES/MANIFEST.json` aggregating SPDX counts
on every release.

## What we don't pretend to do

- We don't check against arbitrary Common Crawl shards. The fingerprint
  of the listed four corpora is what we audit; that's a defensible
  superset of where Inferno content concentrates.
- We don't claim *zero* contamination is achievable on `fs_concepts`,
  because the *concepts* are public knowledge. We claim only that the
  question phrasings are original and that gold answers were chosen
  without consulting model outputs.
