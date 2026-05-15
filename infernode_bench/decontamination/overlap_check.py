"""Decontamination overlap check.

v0 status: stub. Reports the planned corpora and exits 0. IB-18a will
land the minhash pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from infernode_bench.items import load_items

PLANNED_CORPORA = [
    {
        "name": "upstream_inferno_os",
        "source": "bitbucket.org/inferno-os/inferno-os.git",
        "risk": "high",
        "notes": "Public, indexed, almost certainly in Common Crawl.",
    },
    {
        "name": "infernode_self",
        "source": "github.com/pdfinn/infernode-os/infernode",
        "risk": "high",
        "notes": "Pinned submodule of IOL; potentially overlaps Limbo items.",
    },
    {
        "name": "plan9port",
        "source": "github.com/9fans/plan9port",
        "risk": "medium",
        "notes": "Source of truth for Plan 9 idiom C items.",
    },
    {
        "name": "ipm",
        "source": "Inferno Programmer's Manual (LaTeX, Vita Nuova)",
        "risk": "medium",
        "notes": "Authoritative for fs_concepts MCQ — prompts must be original.",
    },
]


def run(output: Path | None = None) -> dict:
    items = load_items()
    manifest = {
        "status": "stub",
        "planned_corpora": PLANNED_CORPORA,
        "n_items_to_audit": len(items),
        "policy": (
            "Flag any item with ≥3 unique 13-grams from prompt or golden "
            "matching a planned corpus. Lifted items must be transformed "
            "(rename, recompose, restructure) or dropped."
        ),
    }
    if output is not None:
        output.write_text(json.dumps(manifest, indent=2) + "\n")
    else:
        json.dump(manifest, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return manifest


if __name__ == "__main__":
    run()
