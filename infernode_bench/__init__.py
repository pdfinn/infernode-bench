"""InferBench — a benchmark for LLMs writing Inferno/InferNode code.

Public surface:

    infernode_bench.load_items()              # full item set
    infernode_bench.load_subset(name)         # subset spec
    infernode_bench.resolve_subset(subset)    # → list[item]
    infernode_bench.validate_item(item)       # raises on schema violation
"""

from infernode_bench.items import (
    REPO_ROOT,
    CATEGORIES,
    load_items,
    load_item_file,
    iter_item_files,
)
from infernode_bench.schema import validate_item, validate_subset
from infernode_bench.subset import load_subset, resolve_subset

__all__ = [
    "REPO_ROOT",
    "CATEGORIES",
    "load_items",
    "load_item_file",
    "iter_item_files",
    "load_subset",
    "resolve_subset",
    "validate_item",
    "validate_subset",
]
