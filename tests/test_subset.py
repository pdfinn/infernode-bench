"""Subset resolution: deterministic, tamper-detectable, covers all built-ins."""

import pytest

from infernode_bench.items import load_items
from infernode_bench.subset import load_subset, resolve_subset, resolved_hash


SUBSETS = ["smoke", "mini", "full"]


@pytest.mark.parametrize("name", SUBSETS)
def test_subset_loads_and_validates(name):
    spec = load_subset(name)
    assert spec["name"] == name


@pytest.mark.parametrize("name", SUBSETS)
def test_subset_resolution_is_deterministic(name):
    spec = load_subset(name)
    items = load_items()
    a = [it["id"] for it in resolve_subset(spec, items)]
    b = [it["id"] for it in resolve_subset(spec, items)]
    assert a == b, "resolve_subset must be deterministic"


def test_smoke_yields_the_migrated_baseline_v2_count():
    # 50 migrated items minus one deprecated (`c_dev_stub_v1` —
    # InferNode kernel-style 9P driver, not testable under plan9port 9c).
    # Tag filter `include_tag: baseline_v2_migration` locks the pool.
    spec = load_subset("smoke")
    items = resolve_subset(spec)
    assert len(items) == 49, (
        f"smoke should contain the 49 active baseline_v2 items, got {len(items)}"
    )
    # Every smoke item must carry the lock tag.
    for it in items:
        assert "baseline_v2_migration" in (it.get("tags") or [])


def test_full_returns_every_non_deprecated_item():
    spec = load_subset("full")
    items = resolve_subset(spec)
    # 150 active items after the IB-11..IB-15 batch-1 expansions.
    assert len(items) >= 100, f"full subset suspiciously small: {len(items)}"


def test_resolved_hash_changes_when_an_item_id_changes():
    spec = load_subset("smoke")
    items = load_items()
    h0 = resolved_hash(resolve_subset(spec, items))
    # Simulate mutating an item: rename one id.
    mutated = []
    flipped = False
    for it in items:
        if not flipped and it["category"] == "limbo_authoring":
            new = dict(it)
            new["id"] = it["id"] + "_mutated"
            mutated.append(new)
            flipped = True
        else:
            mutated.append(it)
    h1 = resolved_hash(resolve_subset(spec, mutated))
    assert h0 != h1


def test_pin_ids_always_included():
    spec = load_subset("smoke")
    spec["pin_ids"] = ["hello_world_v1"]
    spec["exclude_ids"] = ["hello_world_v1"]  # exclude is overridden by pin
    items = resolve_subset(spec)
    ids = {it["id"] for it in items}
    assert "hello_world_v1" in ids


def test_exclude_ids_drops_items():
    spec = load_subset("smoke")
    spec["exclude_ids"] = ["hello_world_v1"]
    items = resolve_subset(spec)
    ids = {it["id"] for it in items}
    assert "hello_world_v1" not in ids
