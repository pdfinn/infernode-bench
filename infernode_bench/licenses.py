"""Per-item SPDX manifest emitter.

Walks `items/**`, aggregates each item's `provenance.spdx` value and
emits `LICENSES/MANIFEST.json` with:

    {
      "bench_sha": "abc123…",
      "n_items": 49,
      "by_license": {"MIT": 49},
      "by_category_license": {"limbo_authoring": {"MIT": 15}, …},
      "items": [{"id":"hello_world_v1", "spdx":"MIT", "authored_by":"human",
                 "derived_from":"eval/scenarios/baseline_v2.yaml"}, …]
    }

The aggregate counts are what the README's license table consumes.
The per-item list is the audit trail.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from infernode_bench.items import REPO_ROOT, load_items


def build_manifest() -> dict:
    items = load_items(include_deprecated=True)
    by_license: Counter[str] = Counter()
    by_cat_lic: dict[str, Counter[str]] = defaultdict(Counter)
    out_items = []
    for it in items:
        prov = it.get("provenance") or {}
        spdx = prov.get("spdx", "UNKNOWN")
        cat = it["category"]
        by_license[spdx] += 1
        by_cat_lic[cat][spdx] += 1
        out_items.append({
            "id": it["id"],
            "category": cat,
            "spdx": spdx,
            "authored_by": prov.get("authored_by"),
            "derived_from": prov.get("derived_from"),
            "source_repo": prov.get("source_repo"),
            "deprecated": bool(it.get("deprecated")),
        })

    try:
        bench_sha = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        bench_sha = "unknown"

    return {
        "bench_sha": bench_sha,
        "n_items": len(items),
        "by_license": dict(by_license),
        "by_category_license": {c: dict(d) for c, d in by_cat_lic.items()},
        "items": sorted(out_items, key=lambda x: (x["category"], x["id"])),
    }


def write_manifest(path: Path | None = None) -> Path:
    manifest = build_manifest()
    if path is None:
        path = REPO_ROOT / "LICENSES" / "MANIFEST.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n")
    return path


def render_table(manifest: dict) -> str:
    """Markdown table of license distribution suitable for the README."""
    lines = ["| License | Count |", "|---------|------:|"]
    for lic, n in sorted(manifest["by_license"].items(),
                         key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{lic}` | {n} |")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None)
    p.add_argument("--print-table", action="store_true")
    args = p.parse_args()
    if args.print_table:
        print(render_table(build_manifest()))
    else:
        path = write_manifest(Path(args.out) if args.out else None)
        print(f"wrote {path}")
