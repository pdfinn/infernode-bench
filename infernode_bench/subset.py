"""Subset resolution.

`subset` files declare what slice of the full item set a run targets.
The resolver is deterministic: given a fixed item set and a subset file,
it always returns the same ordered list. Tampering is detectable by
comparing `resolved_hash` (sha256 of the sorted resolved item IDs).

Sampling algorithm:

    1. Apply `exclude_ids` to remove items.
    2. For each stratum:
        a. Filter the item set to that stratum's category.
        b. If `by` and `ratio` are given, partition further; each partition
           gets `floor(n * ratio_i / sum(ratio))` items, with the
           remainder going to the largest-ratio partition.
        c. Within each partition, shuffle deterministically with the
           subset's `seed` (mixed with the stratum key for independence
           across strata) and pick the top-n.
    3. Add `pin_ids` to the front (de-duped).
    4. Sort the final list by item ID — order matters for `resolved_hash`,
       and lexicographic order is the simplest tamper-detectable choice.

`n` can be the literal string `"all"` to mean every item in the stratum.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Iterable

import yaml

from infernode_bench.items import REPO_ROOT, load_items
from infernode_bench.schema import validate_subset

SUBSETS_DIR = REPO_ROOT / "subsets"


def load_subset(name: str) -> dict:
    path = SUBSETS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"subset spec not found: {path}")
    with path.open() as f:
        subset = yaml.safe_load(f)
    validate_subset(subset)
    return subset


def _stratum_rng_key(seed: int, category: str, partition_key: str | None) -> int:
    """Mix the seed with the stratum descriptor so independent strata don't
    share shuffles."""
    h = hashlib.sha256()
    h.update(seed.to_bytes(8, "little", signed=False))
    h.update(b"\x00")
    h.update(category.encode())
    h.update(b"\x00")
    if partition_key is not None:
        h.update(partition_key.encode())
    return int.from_bytes(h.digest()[:8], "little")


def _take(items: list[dict], n: int, rng_key: int) -> list[dict]:
    """Deterministic top-n selection from items. Items are sorted by ID
    first to make the input order independent of file walk order."""
    items = sorted(items, key=lambda it: it["id"])
    if n >= len(items):
        return items
    rng = random.Random(rng_key)
    return rng.sample(items, n)


def _allocate_quotas(total: int, ratio: dict[str, int]) -> dict[str, int]:
    """Split `total` into integer quotas proportional to ratio. The largest
    ratio gets the remainder."""
    s = sum(ratio.values())
    if s == 0:
        return {k: 0 for k in ratio}
    quotas = {k: math.floor(total * v / s) for k, v in ratio.items()}
    assigned = sum(quotas.values())
    leftover = total - assigned
    if leftover > 0:
        # Hand leftovers to the largest-ratio partitions, breaking ties by key.
        order = sorted(ratio.items(), key=lambda kv: (-kv[1], kv[0]))
        for i in range(leftover):
            quotas[order[i % len(order)][0]] += 1
    return quotas


def resolve_subset(
    subset: dict,
    items: Iterable[dict] | None = None,
) -> list[dict]:
    """Materialise the subset against the item set.

    Returns the chosen items in lexicographic order by ID. The caller
    can re-key via dict comprehension if a different order is wanted.
    """
    if items is None:
        items = load_items()
    items = list(items)

    seed = subset["seed"]
    exclude = set(subset.get("exclude_ids") or ())
    pin = subset.get("pin_ids") or []
    include_tag = subset.get("include_tag")

    # Index by category for fast strata access.
    by_cat: dict[str, list[dict]] = {}
    for item in items:
        if item["id"] in exclude:
            continue
        if include_tag and include_tag not in (item.get("tags") or ()):
            continue
        by_cat.setdefault(item["category"], []).append(item)

    chosen: list[dict] = []
    seen: set[str] = set()

    # 1. Pin first (must exist in the loaded item set).
    by_id = {it["id"]: it for it in items}
    for pid in pin:
        if pid in by_id and pid not in seen:
            chosen.append(by_id[pid])
            seen.add(pid)

    # 2. Strata.
    for stratum in subset["strata"]:
        cat = stratum["category"]
        pool = [it for it in by_cat.get(cat, []) if it["id"] not in seen]
        n = stratum.get("n", "all")
        if n == "all" or n is None:
            picks = sorted(pool, key=lambda it: it["id"])
        else:
            ratio = stratum.get("ratio")
            partition_by = stratum.get("by")
            if ratio and partition_by:
                buckets: dict[str, list[dict]] = {}
                for it in pool:
                    key = str(it.get(partition_by, ""))
                    buckets.setdefault(key, []).append(it)
                quotas = _allocate_quotas(int(n), ratio)
                picks = []
                for bucket_key, quota in quotas.items():
                    bucket = buckets.get(bucket_key, [])
                    rng_key = _stratum_rng_key(seed, cat, bucket_key)
                    picks.extend(_take(bucket, quota, rng_key))
            else:
                rng_key = _stratum_rng_key(seed, cat, None)
                picks = _take(pool, int(n), rng_key)
        for it in picks:
            if it["id"] not in seen:
                chosen.append(it)
                seen.add(it["id"])

    chosen.sort(key=lambda it: it["id"])
    return chosen


def resolved_hash(items: list[dict]) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(it["id"].encode())
        h.update(b"\n")
    return h.hexdigest()
