"""Verify every item's golden against its declared grader.

For compile_gate items: pipe golden.source through IOL's local.sh
under GATE_LANG. PASS iff the gate returns ok=true.

For trace_match items: parse golden.trace; PASS iff it is structurally
valid (non-empty list of {op, path, ...} dicts with op in {read, write,
walk, open, stat}).

For mcq items: PASS iff golden.answer is a letter A..<n_choices>.

For judge items: PASS iff golden.exemplar is present (the judge itself
isn't invoked here — too expensive for CI; tracked under IB-17).

Items with `needs_golden: true` are reported as SKIP, not FAIL.

Usage:
    python -m infernode_bench verify
    python -m infernode_bench verify --category limbo_authoring
    python -m infernode_bench verify --strict        # fail on any SKIP too

Exit codes:
    0 — every active item PASS/SKIP per policy
    1 — at least one item FAIL (or SKIP under --strict)
    2 — environment problem (gate unreachable, etc.)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter

from infernode_bench.graders.compile_gate import (
    GateUnavailable,
    _resolve_iol_root,
)
from infernode_bench.items import CATEGORIES, load_items

_VALID_OPS = {"read", "write", "walk", "open", "stat"}


def _gate_source(source: str, gate_lang: str, timeout_s: float = 60.0) -> dict:
    iol = _resolve_iol_root()
    gate = iol / "tools" / "compile_gate" / "local.sh"
    env = {**os.environ, "GATE_LANG": gate_lang}
    proc = subprocess.run(
        [str(gate)],
        input=source.encode(),
        capture_output=True,
        env=env,
        timeout=timeout_s,
    )
    try:
        line = proc.stdout.decode().strip().splitlines()[-1]
        return json.loads(line)
    except (IndexError, ValueError):
        return {
            "ok": False,
            "stderr": (
                f"gate emitted no JSON. exit={proc.returncode} "
                f"stderr={proc.stderr.decode(errors='replace')[:500]}"
            ),
        }


def verify_one(item: dict) -> tuple[str, str]:
    """Return (verdict, detail) where verdict ∈ {PASS, FAIL, SKIP}."""
    if item.get("needs_golden"):
        return "SKIP", "needs_golden"
    if item.get("deprecated"):
        return "SKIP", "deprecated"

    grader = item["grader"]
    kind = grader["kind"]
    golden = item.get("golden")

    if not golden:
        return "FAIL", "no golden but not flagged needs_golden"

    if kind == "compile_gate":
        gate_lang = grader["config"]["gate_lang"]
        source = golden.get("source")
        if not source:
            return "FAIL", "compile_gate golden missing `source`"
        r = _gate_source(source, gate_lang)
        if r.get("ok"):
            return "PASS", f"{gate_lang} dis_size={r.get('dis_size')}"
        stderr = (r.get("stderr") or "").splitlines()
        head = stderr[0] if stderr else ""
        return "FAIL", f"{gate_lang}: {head[:200]}"

    if kind == "trace_match":
        trace = golden.get("trace")
        if not isinstance(trace, list) or not trace:
            return "FAIL", "trace_match golden missing/empty `trace`"
        for i, step in enumerate(trace):
            if not isinstance(step, dict):
                return "FAIL", f"trace[{i}] is not a dict"
            if step.get("op") not in _VALID_OPS:
                return "FAIL", f"trace[{i}].op={step.get('op')!r} not in {_VALID_OPS}"
            if not step.get("path"):
                return "FAIL", f"trace[{i}] missing path"
        return "PASS", f"trace n={len(trace)}"

    if kind == "mcq":
        ans = (golden.get("answer") or "").strip().upper()
        n_choices = len(grader["config"]["choices"])
        if len(ans) != 1 or not ("A" <= ans <= chr(ord("A") + n_choices - 1)):
            return "FAIL", f"mcq answer={ans!r} not in A..{chr(ord('A') + n_choices - 1)}"
        return "PASS", f"answer={ans}"

    if kind == "judge":
        if not golden.get("exemplar"):
            return "FAIL", "judge golden missing `exemplar`"
        return "PASS", f"exemplar chars={len(golden['exemplar'])}"

    return "FAIL", f"unknown grader kind: {kind!r}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--category", default=None,
                   help="restrict to one category")
    p.add_argument("--strict", action="store_true",
                   help="fail on any SKIP, not just FAIL")
    p.add_argument("--quiet", action="store_true",
                   help="only print verdicts + final summary")
    p.add_argument("--json", action="store_true",
                   help="emit one JSON line per item to stdout")
    args = p.parse_args(argv)

    if args.category and args.category not in CATEGORIES:
        print(f"unknown category: {args.category}", file=sys.stderr)
        return 2

    try:
        _resolve_iol_root()
    except GateUnavailable as e:
        print(f"gate unavailable: {e}", file=sys.stderr)
        return 2

    items = load_items(category=args.category, include_deprecated=True)
    items.sort(key=lambda it: (it["category"], it["id"]))

    n = Counter()
    fails: list[tuple[str, str, str]] = []
    for item in items:
        verdict, detail = verify_one(item)
        n[verdict] += 1
        if args.json:
            print(json.dumps({
                "item_id": item["id"],
                "category": item["category"],
                "verdict": verdict,
                "detail": detail,
            }))
            continue
        flag = {"PASS": "✓", "FAIL": "✗", "SKIP": "·"}[verdict]
        if not args.quiet or verdict != "PASS":
            print(f"  {flag} {verdict:5s} {item['category']:18s} {item['id']:35s}  {detail}")
        if verdict == "FAIL":
            fails.append((item["id"], item["category"], detail))

    total = sum(n.values())
    print(f"\n{n['PASS']}/{total} PASS  ({n['FAIL']} FAIL, {n['SKIP']} SKIP)",
          file=sys.stderr)

    if n["FAIL"]:
        print("\nFailures:", file=sys.stderr)
        for sid, cat, detail in fails:
            print(f"  {cat:18s} {sid}: {detail}", file=sys.stderr)

    if n["FAIL"]:
        return 1
    if args.strict and n["SKIP"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
