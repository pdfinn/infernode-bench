"""Schema validation for every checked-in item."""

from collections import Counter

import pytest

from infernode_bench.items import load_items
from infernode_bench.schema import iter_item_errors, validate_item


@pytest.fixture(scope="module")
def items():
    return load_items(include_deprecated=True)


def test_every_item_validates_against_schema(items):
    failures = []
    for it in items:
        errors = list(iter_item_errors(it))
        if errors:
            failures.append(
                (it.get("id", "<unknown>"),
                 [(".".join(str(p) for p in e.absolute_path) or "<root>", e.message)
                  for e in errors])
            )
    assert not failures, f"schema failures: {failures}"


def test_item_ids_are_unique(items):
    counts = Counter(it["id"] for it in items)
    dupes = [k for k, v in counts.items() if v > 1]
    assert not dupes, f"duplicate item ids: {dupes}"


def test_at_least_one_item_per_category(items):
    cats = {it["category"] for it in items}
    expected = {"limbo_authoring", "plan9_c", "inferno_sh",
                "9p_tool_use", "fs_concepts"}
    assert expected <= cats, f"missing categories: {expected - cats}"


def test_validate_item_accepts_a_well_formed_record():
    item = {
        "id": "fixture_v1",
        "category": "limbo_authoring",
        "difficulty": "easy",
        "prompt": "write hello world",
        "grader": {"kind": "compile_gate", "config": {"gate_lang": "limbo"}},
        "needs_golden": True,
        "provenance": {"authored_by": "human", "spdx": "MIT"},
    }
    validate_item(item)
