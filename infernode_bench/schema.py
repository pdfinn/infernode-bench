"""JSON Schema validation for items and subsets.

Loads the JSON Schema docs from `schema/` once, exposes validators that
raise `jsonschema.ValidationError` on failure with the offending item's
id surfaced in the message.
"""

from __future__ import annotations

import json
from functools import lru_cache

from jsonschema import Draft202012Validator

from infernode_bench.items import REPO_ROOT

SCHEMA_DIR = REPO_ROOT / "schema"


@lru_cache(maxsize=4)
def _validator(name: str) -> Draft202012Validator:
    path = SCHEMA_DIR / f"{name}.schema.json"
    with path.open() as f:
        schema = json.load(f)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_item(item: dict) -> None:
    _validator("item").validate(item)


def validate_subset(subset: dict) -> None:
    _validator("subset").validate(subset)


def iter_item_errors(item: dict):
    return _validator("item").iter_errors(item)
