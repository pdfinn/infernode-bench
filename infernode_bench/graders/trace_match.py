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
#
# Two extraction modes are stacked:
#   - Limbo idiom: `fd := sys->open("/tool/X/ctl", MODE)` binds the path
#     to fd, then later `sys->read(fd, …)` / `sys->write(fd, …)` /
#     `sys->fprint(fd, …)` use the binding (IOL-35).
#   - rc / inline idiom: `echo args > /tool/X/ctl` or
#     `cat /tool/X/ctl` carries the path inline with the verb.
#
# Before either pass, string-literal contents are blanked out so paths
# inside `sys->fprint(…, "cannot read /tool/X/ctl: %r\n")` error messages
# don't get scored as real I/O (IOL-36).

# Path that appears with the verb inline. Two forms covered:
#   - Function call:  write("/tool/X/ctl", data) / fprint(.../path) / put("/path")
#   - Shell redirect: ... > /tool/X/ctl  (rc append `>>` also)
_WRITE_CALL_RE = re.compile(
    r"""(?:write|fprint|put)\s*\(\s*['"](?P<path>/tool/[\w./-]+)['"]\s*[,)]\s*['"]?(?P<data>[^'")\n]*)""",
    re.IGNORECASE,
)
_WRITE_REDIR_RE = re.compile(
    r""">+\s*['"]?(?P<path>/tool/[\w./-]+)['"]?""",
)
_READ_INLINE_RE = re.compile(
    r"""(?:read|cat|getb|gets)\s+['"]?(?P<path>/tool/[\w./-]+)['"]?""",
    re.IGNORECASE,
)
_READ_REDIR_RE = re.compile(
    r"""<\s*['"]?(?P<path>/tool/[\w./-]+)['"]?""",
)

# Limbo `open()` binding: `lhs := (sys->)?open("/tool/…", MODE)`
_OPEN_BIND_RE = re.compile(
    r"""(?P<lhs>\b\w+\b)\s*:?=\s*(?:sys\s*->\s*)?open\s*\(\s*['"](?P<path>/tool/[\w./-]+)['"]""",
    re.IGNORECASE,
)
# Op against a previously-bound fd. Covers:
#   sys->read(fd, …) / sys->write(fd, …) / sys->fprint(fd, fmt, …)
_FD_OP_RE = re.compile(
    r"""(?:sys\s*->\s*)?(?P<op>read|write|fprint)\s*\(\s*(?P<fd>\b\w+\b)\s*[,)]""",
    re.IGNORECASE,
)
# Limbo string-literal variable assignment: `name := "literal"`. Used to
# fill in `data` for fd-based writes whose payload is a variable that was
# assigned a literal somewhere in scope (e.g. `args := "*.b /appl/veltro"`).
_STR_ASSIGN_RE = re.compile(
    r"""(?P<lhs>\b\w+\b)\s*:?=\s*['"](?P<val>[^'"\n]+)['"]""",
)

_FENCED_TRACE_RE = re.compile(
    r"```(?:trace|json)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _blank_string_literals(source: str) -> str:
    """Return ``source`` with the *contents* of double-quoted string
    literals replaced by spaces, preserving overall offsets. Backslash-
    escaped quotes inside the literal are handled.

    Stripping string contents lets the static scanners safely ignore
    paths that appear only inside error-message format strings — these
    are I/O of text *about* the path, not I/O *against* it.

    Single quotes are intentionally NOT treated as string delimiters:
    in Limbo `'x'` is a single-character literal, never a string; and
    in code comments / prose, apostrophes ("Veltro's tool") would
    otherwise blank everything between the apostrophe and end-of-input.
    rc shell does use `'…'` for strings, but paths inside rc strings
    are rare enough that we accept the rare false positive over the
    everything-after-an-apostrophe false negative.
    """
    chars = list(source)
    i = 0
    n = len(chars)
    while i < n:
        c = chars[i]
        if c == '"':
            j = i + 1
            while j < n:
                if chars[j] == "\\" and j + 1 < n:
                    chars[j] = " "
                    chars[j + 1] = " "
                    j += 2
                    continue
                if chars[j] == '"':
                    break
                chars[j] = " "
                j += 1
            i = j + 1
        else:
            i += 1
    return "".join(chars)


def _extract_write_data(
    orig_call_tail: str,
    blanked_rest: str,
    var_strings: dict,
    inline_str_re: "re.Pattern",
    format_spec_re: "re.Pattern",
) -> str:
    """Reconstruct the ``data`` field of a write op from a Limbo call's
    argument tail. Three cases are recognised, in order:

    1.  ``fprint(fd, "%s", args)`` — first inline literal is a format
        string (matches ``%[type]``); the data is the *next* argument.
        If that arg is a bareword and we saw ``args := "..."`` earlier,
        substitute the literal.
    2.  ``write(fd, "literal")`` / ``fprint(fd, "literal\\n")`` — first
        inline literal contains no format specifier; treat the literal
        itself as the data.
    3.  ``write(fd, args, len args)`` — no inline literal; data comes
        from the bareword if it's in the assignment map. Otherwise the
        data is unknown — leave empty for ``data_wildcard`` items to
        accept.
    """
    inline_strings = list(inline_str_re.finditer(orig_call_tail))
    if inline_strings:
        first = inline_strings[0].group("data")
        if format_spec_re.search(first):
            # Format string. Find the bareword after it in the blanked rest.
            after = blanked_rest[blanked_rest.find(",") + 1:]  # skip first arg
            after = after[after.find(",") + 1:]  # skip format-string arg
            bare = re.match(r"\s*\b(\w+)\b\s*$", after.strip(", \t)"))
            if bare and bare.group(1) in var_strings:
                return var_strings[bare.group(1)]
            return ""
        # Not a format string — first literal IS the data.
        return first
    # No inline literal. Try bareword → literal-assignment substitution.
    rest = blanked_rest.strip(", \t")
    if rest:
        last = rest.split(",")[-1].strip()
        bare = re.match(r"\b(\w+)\b\s*$", last)
        if bare and bare.group(1) in var_strings:
            return var_strings[bare.group(1)]
    return ""


def extract_trace(response: str) -> list[dict]:
    """Pull a trace out of the model output. Prefers a fenced JSON block;
    falls back to a static scan that recognises both rc-style inline-path
    I/O and Limbo open-bind-then-fd-op I/O, while ignoring matches that
    fall inside string literals (so error-message paths don't count).
    """
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

    code = _blank_string_literals(response)

    # Pass 1: collect fd → path bindings from open() calls. Run against
    # the *original* response — the path argument is itself a string
    # literal, so it gets blanked in `code` and we lose it there.
    # Open() calls don't appear inside string literals in legitimate
    # code, so over-matching from error messages isn't a real concern.
    bindings: dict[str, str] = {}
    for mb in _OPEN_BIND_RE.finditer(response):
        bindings[mb.group("lhs")] = mb.group("path")

    # Pass 2: collect string-literal assignments so fd writes that hand
    # off a variable (e.g. `args := "*.b /appl/veltro"; sys->fprint(fd,
    # "%s", args)`) can reconstruct the data field. We have to read the
    # *original* response here, before string-blanking removed the
    # literal contents.
    var_strings: dict[str, str] = {}
    for ms in _STR_ASSIGN_RE.finditer(response):
        var_strings.setdefault(ms.group("lhs"), ms.group("val"))

    events: list[tuple[int, dict]] = []  # (start_offset, op_dict)

    # Pass 3: fd-based ops. Two surface forms are accepted:
    #
    #   sys->read(fd, …)  /  sys->write(fd, …)  /  sys->fprint(fd, …)
    #   fd.read(…)        /  fd.write(…)        /  fd.fprint(…)
    #
    # The second form is the Limbo Sys.FD method-call style — `fd` is a
    # ref Sys->FD and has read/write methods. Both forms denote real I/O
    # against the path bound to `fd` by an earlier open(). For writes,
    # we recover the `data` field by inspecting the call's argument tail
    # against the *original* response (the blanker strips string-literal
    # bodies — so inline literal data has to be matched off-blanked).
    _FD_OP_TAIL_RE = re.compile(
        r"""(?:(?:sys\s*->\s*)?(?P<op_a>read|write|fprint)\s*\(\s*(?P<fd_a>\b\w+\b)
            |  (?P<fd_b>\b\w+\b)\s*\.\s*(?P<op_b>read|write|fprint)\s*\(
            )\s*(?P<rest>[^\n)]*)""",
        re.IGNORECASE | re.VERBOSE,
    )
    # Inline double-quoted string literal in the call tail (off-blanked
    # so we get the actual content).
    _INLINE_STR_RE = re.compile(r'"(?P<data>[^"\n]*)"')
    _FORMAT_SPEC_RE = re.compile(r"%[-+# 0]*\d*\.?\d*[diouxXfFeEgGsScCr]")
    for mf in _FD_OP_TAIL_RE.finditer(code):
        fd = mf.group("fd_a") or mf.group("fd_b")
        if fd is None or fd not in bindings:
            continue
        op_name = (mf.group("op_a") or mf.group("op_b") or "").lower()
        # fprint(fd, …) is a write semantically
        op = "write" if op_name in ("write", "fprint") else "read"
        entry: dict = {"op": op, "path": bindings[fd]}
        if op == "write":
            data = _extract_write_data(
                response[mf.start():mf.end()],
                mf.group("rest"),
                var_strings,
                _INLINE_STR_RE,
                _FORMAT_SPEC_RE,
            )
            entry["data"] = data
        events.append((mf.start(), entry))

    # Pass 4: inline-path ops (covers function-call I/O with an inline
    # path AND rc-style shell redirection like `echo X > /tool/Y/ctl`).
    for mw in _WRITE_CALL_RE.finditer(code):
        events.append((
            mw.start(),
            {"op": "write", "path": mw.group("path"),
             "data": mw.group("data").strip()},
        ))
    for mw in _WRITE_REDIR_RE.finditer(code):
        # rc data is whatever came before the `>` — too noisy to extract
        # reliably, leave it empty.
        events.append((mw.start(),
                       {"op": "write", "path": mw.group("path"),
                        "data": ""}))
    for mr in _READ_INLINE_RE.finditer(code):
        events.append((
            mr.start(),
            {"op": "read", "path": mr.group("path")},
        ))
    for mr in _READ_REDIR_RE.finditer(code):
        events.append((mr.start(),
                       {"op": "read", "path": mr.group("path")}))

    # Deduplicate ops that map to the same (op, path, start-region) since
    # the fd-pass and inline-pass occasionally fire on the same line.
    seen: set[tuple[int, str, str]] = set()
    out: list[dict] = []
    for start, op in sorted(events, key=lambda x: x[0]):
        key = (start // 32, op["op"], op["path"])
        if key in seen:
            continue
        seen.add(key)
        out.append(op)
    return out


def _step_key(step: dict) -> tuple:
    return (step.get("op"), step.get("path"), step.get("data", ""))


def _apply_equivalences(trace: list[dict], classes: Iterable[str]) -> list[dict]:
    out = list(trace)
    for cls in classes or ():
        if cls == "data_wildcard":
            # Strip the `data` field from every step. Use this for items
            # whose write payload is runtime-determined (e.g. comes from
            # argv or a computed string) — the bench has no way to know
            # what the value should be statically, and demanding it
            # under `max_edit_distance: 0` makes every such item
            # uninstrumentable. Apply both to `out` and to the golden in
            # `grade_trace_match` so the comparison is symmetric.
            out = [{k: v for k, v in s.items() if k != "data"} for s in out]
            continue
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
