"""Trace-match grader for `9p_tool_use`.

Per IB-8. The headline grader for the headline category, and the only
one without a trivial automatic baseline. v0 implementation covers:

    - Parse a model response that emits a 9P trace, either as code we
      can statically scan for `read`/`write` of `/tool/<name>/{ctl,doc,…}`,
      or as a structured JSON trace block.
    - Compare against item.golden.trace using edit distance.
    - Allow a per-item `max_edit_distance` slack.

Equivalence-class DSL (IB-8b) is stubbed: items can declare
`equivalence_classes: [reorder_writes, ...]` and the matcher applies
named transforms before scoring. The two transforms shipped in v0:

    reorder_writes      writes against distinct paths may be reordered
    drop_redundant_read consecutive reads of the same path collapse to one

Until the v1 9P items land with goldens, this grader is exercised only
by tests; production runs against the migrated baseline items will
short-circuit to needs_golden in the runner.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable

from infernode_bench.graders import GradeResult

# Static-scan patterns for code that drives /tool/<name>/ctl. These are
# best-effort — production-grade trace extraction needs an in-process
# Veltro tool mock (IB-8a).
_WRITE_CTL_RE = re.compile(
    r"""(?:write|fprint|put)\s*\(?\s*['"]?(?P<path>/tool/[\w./-]+)['"]?\s*[,)]\s*['"]?(?P<data>[^'")\n]*)""",
    re.IGNORECASE,
)
_READ_CTL_RE = re.compile(
    r"""(?:read|cat|getb|gets)\s*\(?\s*['"]?(?P<path>/tool/[\w./-]+)['"]?""",
    re.IGNORECASE,
)
_FENCED_TRACE_RE = re.compile(
    r"```(?:trace|json)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_trace(response: str) -> list[dict]:
    """Pull a trace out of the model output. Prefers a fenced JSON block;
    falls back to static scan."""
    if not response:
        return []
    m = _FENCED_TRACE_RE.search(response)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list) and all(
                isinstance(x, dict) and "op" in x and "path" in x for x in data
            ):
                return data
        except json.JSONDecodeError:
            pass
    out: list[dict] = []
    for m in _WRITE_CTL_RE.finditer(response):
        out.append({"op": "write", "path": m.group("path"), "data": m.group("data").strip()})
    for m in _READ_CTL_RE.finditer(response):
        out.append({"op": "read", "path": m.group("path")})
    return out


def _step_key(step: dict) -> tuple:
    return (step.get("op"), step.get("path"), step.get("data", ""))


def _apply_equivalences(trace: list[dict], classes: Iterable[str]) -> list[dict]:
    out = list(trace)
    for cls in classes or ():
        if cls == "drop_redundant_read":
            collapsed: list[dict] = []
            for step in out:
                if (collapsed and step.get("op") == "read" and
                        collapsed[-1].get("op") == "read" and
                        collapsed[-1].get("path") == step.get("path")):
                    continue
                collapsed.append(step)
            out = collapsed
        elif cls == "reorder_writes":
            # Bucket consecutive writes-to-distinct-paths and sort them.
            buf: list[dict] = []
            new: list[dict] = []
            for step in out:
                if step.get("op") == "write":
                    buf.append(step)
                else:
                    if buf:
                        new.extend(sorted(buf, key=_step_key))
                        buf.clear()
                    new.append(step)
            if buf:
                new.extend(sorted(buf, key=_step_key))
            out = new
    return out


def edit_distance(a: list[dict], b: list[dict]) -> int:
    """Levenshtein on lists of trace steps, comparing by (op, path, data)."""
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        ak = _step_key(a[i - 1])
        for j in range(1, n + 1):
            cost = 0 if ak == _step_key(b[j - 1]) else 1
            cur[j] = min(
                prev[j] + 1,        # deletion
                cur[j - 1] + 1,     # insertion
                prev[j - 1] + cost, # substitution
            )
        prev = cur
    return prev[n]


def grade_trace_match(item: dict, response: str) -> GradeResult:
    t0 = time.monotonic()
    cfg = item.get("grader", {}).get("config", {}) or {}
    max_dist = int(cfg.get("max_edit_distance", 0))
    classes = cfg.get("equivalence_classes") or ()

    golden = (item.get("golden") or {}).get("trace")
    if golden is None:
        return GradeResult(
            ok=False, kind="trace_match",
            detail={"reason": "item has no golden trace; needs_golden"},
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )

    actual = extract_trace(response or "")
    a_norm = _apply_equivalences(actual, classes)
    g_norm = _apply_equivalences(golden, classes)
    dist = edit_distance(g_norm, a_norm)
    ok = dist <= max_dist

    return GradeResult(
        ok=ok, kind="trace_match",
        score=1.0 if ok else 0.0,
        detail={
            "distance": dist,
            "max_edit_distance": max_dist,
            "actual_trace": actual,
            "actual_steps": len(actual),
            "expected_steps": len(golden),
        },
        elapsed_ms=int((time.monotonic() - t0) * 1000),
    )
