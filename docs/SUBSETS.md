# Subsets

Three subsets ship at v0. All three are deterministic samples of the
underlying item set, keyed by `(name, seed, item_set_hash)`.

| Subset | Items target | Use                                                             |
|--------|-------------:|-----------------------------------------------------------------|
| smoke  |       ~50    | Quick sanity check; one-to-one with IOL's `baseline_v2.yaml`.   |
| mini   |      ~150    | Default published headline number.                              |
| full   |     ~800+    | Everything public — used for the published leaderboard rows.    |

## Resolver

`infernode_bench/subset.py:resolve_subset(spec)` materialises a subset:

1. Apply `exclude_ids`.
2. For each stratum, take `n` items from that category. If the stratum
   declares `by` + `ratio`, the count is split between buckets
   (`difficulty` or `subcategory`); each bucket draws deterministically
   from its share.
3. Add `pin_ids` to the front, deduped.
4. Sort by item ID. The sorted ID list is hashed (sha256) and that hash
   is recorded in every result row.

Determinism is mixed in via `sha256(seed || category || bucket_key)` so
each stratum's shuffle is independent.

## How sub-150-item subsets behave during v0

The current item set is 50 items (the migrated `baseline_v2`). The
`mini` strata sum to 150 — bigger than what's available. The resolver
returns the available items, capped by each stratum's `n`. As items
land under IB-11..IB-15, `mini` begins to differ from `smoke`.

## Adding a subset

1. Drop `subsets/<name>.yaml` with the schema in
   `schema/subset.schema.json`. Pick a *new* seed so the sample is
   independent of existing subsets.
2. `python -m infernode_bench subset resolve <name>` to materialise.
3. The first row in the resulting leaderboard pins the resolved hash —
   future rows must match or the leaderboard runner flags a drift.

## Bumping a subset

Editing an existing subset spec is allowed (e.g. to grow `mini` to 250
after Phase 2). It changes the `resolved_hash`. Leaderboard rows pin
the hash they ran against, so historical rows stay comparable;
post-bump rows are tagged with the new hash. Don't try to keep an old
hash "alive" by adjusting items to compensate — bump the subset version
in its filename if you need a frozen historical handle.
