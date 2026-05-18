"""Item loading. Walks `items/<category>/*.yaml`, loads, returns flat list."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ITEMS_DIR = REPO_ROOT / "items"

CATEGORIES = (
    "limbo_authoring",
    "plan9_c",
    "inferno_sh",
    "9p_tool_use",
    "fs_concepts",
)


def iter_item_files(category: str | None = None) -> Iterator[Path]:
    """Yield every items/**/*.yaml path. If `category` is given, restrict to it."""
    if category is not None:
        roots = [ITEMS_DIR / category]
    else:
        roots = [ITEMS_DIR / c for c in CATEGORIES]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.yaml")):
            yield path


def load_item_file(path: Path) -> list[dict]:
    """Load one YAML item file. Returns the list under the top-level `items:` key."""
    with path.open() as f:
        data = yaml.safe_load(f)
    if data is None:
        return []
    if not isinstance(data, dict) or "items" not in data:
        raise ValueError(f"{path}: missing top-level `items:` list")
    items = data["items"]
    if not isinstance(items, list):
        raise ValueError(f"{path}: `items:` is not a list")
    return items


def load_items(category: str | None = None,
               include_deprecated: bool = False) -> list[dict]:
    """Load all items, flattened across files."""
    out: list[dict] = []
    for path in iter_item_files(category=category):
        for item in load_item_file(path):
            if not include_deprecated and item.get("deprecated"):
                continue
            out.append(item)
    return out
