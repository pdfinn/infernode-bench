"""Decontamination overlap check.

For each item's prompt and golden text, compute the set of normalised
k-grams and check how many appear in each candidate corpus. Items with
≥ THRESHOLD unique k-grams matching a corpus are flagged for review.

Corpora (configurable via env vars; missing corpora are skipped, not
fatal — the manifest records which were checked):

    INFERBENCH_UPSTREAM_INFERNO   path to a Vita Nuova inferno-os clone
    INFERBENCH_INFERNODE          path to the InferNode tree
                                  (default: $INFERNODE_OS_LLM/infernode)
    INFERBENCH_PLAN9PORT          path to a plan9port clone
    INFERBENCH_IPM_DIR            path to Inferno Programmer's Manual
                                  sources (any directory of text files)

The corpus walker indexes any of: `*.b *.m *.c *.h *.sh *.rc *.md *.txt`
and the IPM man pages (no extension, troff source).

Output: `docs/DECONTAMINATION-REPORT.json` (and `.md` summary).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

from infernode_bench.items import REPO_ROOT, load_items

K = 13          # n-gram size in normalised tokens
THRESHOLD = 3   # min unique k-grams matching a corpus to flag
SUFFIXES = (".b", ".m", ".c", ".h", ".sh", ".rc", ".md", ".txt", "")

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S")


def _tokenize(text: str) -> list[str]:
    """Cheap tokeniser — preserves identifiers, splits on whitespace and
    punctuation, lowercases. Good enough for k-gram fingerprinting."""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _kgrams(tokens: list[str], k: int = K) -> Iterator[str]:
    """Yield k-gram strings (joined with single spaces)."""
    if len(tokens) < k:
        return
    for i in range(len(tokens) - k + 1):
        yield " ".join(tokens[i:i + k])


def _kgram_hashes(text: str, k: int = K) -> set[int]:
    """Return a set of 64-bit truncated sha256 hashes of k-grams.
    Smaller in memory than the string set itself."""
    out: set[int] = set()
    tokens = _tokenize(text)
    for kg in _kgrams(tokens, k):
        h = hashlib.sha256(kg.encode()).digest()[:8]
        out.add(int.from_bytes(h, "little"))
    return out


def _iter_corpus_files(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in SUFFIXES:
            try:
                if path.stat().st_size > 1_000_000:   # skip huge files
                    continue
                yield path
            except OSError:
                continue


def build_corpus_index(root: Path, k: int = K) -> set[int]:
    """Aggregate k-gram hashes across every file under `root`."""
    index: set[int] = set()
    n_files = 0
    for path in _iter_corpus_files(root):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        index |= _kgram_hashes(text, k)
        n_files += 1
    print(f"  indexed {n_files} files / {len(index)} unique {k}-grams from {root}",
          file=sys.stderr)
    return index


# We score prompt-overlap and golden-overlap separately and flag mainly
# on prompt-overlap. Goldens are constrained by language conventions —
# every Limbo program shares the same `include "sys.m"; sys = load Sys
# Sys->PATH; init: fn(nil: ref Draw->Context, ...)` boilerplate, so
# golden-side k-grams pick up tens of matches against InferNode's
# canonical examples without any actual content overlap. The novel
# information that needs protecting is the *prompt phrasing*; if a
# prompt's substantive 13-grams appear verbatim in a corpus the model
# might have trained on, that's the contamination risk.

PROMPT_THRESHOLD = 3       # flag if a prompt has this many shared k-grams
GOLDEN_THRESHOLD = 30      # informational; goldens almost always match


def item_prompt(item: dict) -> str:
    return item.get("prompt", "")


def item_golden_text(item: dict) -> str:
    golden = item.get("golden") or {}
    parts: list[str] = []
    if "source" in golden:
        parts.append(golden["source"])
    if "exemplar" in golden:
        parts.append(golden["exemplar"])
    return "\n".join(parts)


def run(args: argparse.Namespace) -> int:
    corpora_paths = {
        "upstream_inferno_os": os.environ.get("INFERBENCH_UPSTREAM_INFERNO"),
        "infernode": (os.environ.get("INFERBENCH_INFERNODE")
                      or (f"{os.environ.get('INFERNODE_OS_LLM', '')}/infernode"
                          if os.environ.get("INFERNODE_OS_LLM") else None)),
        "plan9port": os.environ.get("INFERBENCH_PLAN9PORT"),
        "ipm": os.environ.get("INFERBENCH_IPM_DIR"),
    }
    indices: dict[str, set[int]] = {}
    checked: list[dict] = []
    skipped: list[dict] = []
    for name, p in corpora_paths.items():
        info = {"name": name, "path": p}
        if not p or not Path(p).is_dir():
            info["status"] = "skipped (path missing)"
            skipped.append(info)
            continue
        print(f"indexing corpus: {name} ({p})", file=sys.stderr)
        indices[name] = build_corpus_index(Path(p))
        info["status"] = "ok"
        info["n_kgrams"] = len(indices[name])
        checked.append(info)

    items = load_items(include_deprecated=False)
    rows = []
    flagged: list[dict] = []
    for item in items:
        prompt_hashes = _kgram_hashes(item_prompt(item))
        golden_hashes = _kgram_hashes(item_golden_text(item))
        prompt_overlap = {c: len(prompt_hashes & idx) for c, idx in indices.items()}
        golden_overlap = {c: len(golden_hashes & idx) for c, idx in indices.items()}
        row = {
            "id": item["id"],
            "category": item["category"],
            "n_prompt_kgrams": len(prompt_hashes),
            "n_golden_kgrams": len(golden_hashes),
            "prompt_overlap": prompt_overlap,
            "golden_overlap": golden_overlap,
        }
        rows.append(row)
        flag_corpora = [c for c, n in prompt_overlap.items()
                        if n >= PROMPT_THRESHOLD]
        if flag_corpora:
            flagged.append({**row, "flagged_against": flag_corpora,
                            "reason": "prompt k-gram overlap"})

    summary = {
        "k": K,
        "prompt_threshold": PROMPT_THRESHOLD,
        "golden_threshold": GOLDEN_THRESHOLD,
        "policy": (
            "Flag on prompt overlap only. Goldens share idiomatic "
            "boilerplate (include statements, init signatures) with the "
            "InferNode tree by construction — that's not contamination."
        ),
        "corpora_checked": checked,
        "corpora_skipped": skipped,
        "n_items": len(items),
        "n_flagged": len(flagged),
        "flagged": flagged,
        "rows": rows,
    }

    out_dir = REPO_ROOT / "docs"
    json_path = out_dir / "DECONTAMINATION-REPORT.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    md_path = out_dir / "DECONTAMINATION-REPORT.md"
    md_lines = [
        "# Decontamination report",
        "",
        f"- k-gram size: {K}",
        f"- prompt-overlap threshold (flag if ≥): {PROMPT_THRESHOLD}",
        f"- golden-overlap threshold (informational): {GOLDEN_THRESHOLD}",
        f"- items audited: {len(items)}",
        f"- items flagged (on prompt overlap): {len(flagged)}",
        "",
        f"Policy: {summary['policy']}",
        "",
        "## Corpora",
        "",
        "| Corpus | Path | Status | k-grams |",
        "|--------|------|--------|--------:|",
    ]
    for c in checked + skipped:
        md_lines.append(
            f"| {c['name']} | `{c.get('path') or '—'}` | "
            f"{c['status']} | {c.get('n_kgrams', '—')} |"
        )
    md_lines += ["", "## Flagged items", ""]
    if not flagged:
        md_lines.append("None — no prompt overlaps any corpus at threshold.")
    else:
        md_lines.append("| Item | Category | Flagged against | Top prompt overlap |")
        md_lines.append("|------|----------|------------------|-------------------:|")
        for f in flagged:
            top = max(f["prompt_overlap"].items(), key=lambda kv: kv[1])
            md_lines.append(
                f"| `{f['id']}` | {f['category']} | "
                f"{', '.join(f['flagged_against'])} | {top[0]}={top[1]} |"
            )
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"\nwrote {json_path}", file=sys.stderr)
    print(f"wrote {md_path}", file=sys.stderr)
    print(f"\n{len(flagged)} item(s) flagged out of {len(items)}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    args = p.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
