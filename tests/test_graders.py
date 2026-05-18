"""Grader unit tests. Each grader has a small fixture-driven contract:
the dispatch function returns a `GradeResult` with the expected `ok`
and `kind`."""

import pytest

from infernode_bench.graders import grade
from infernode_bench.graders.mcq import extract_letter, grade_mcq
from infernode_bench.graders.trace_match import (
    edit_distance,
    extract_trace,
    grade_trace_match,
)


# ----- MCQ ---------------------------------------------------------------

@pytest.mark.parametrize("response, expected", [
    ("B", "B"),
    ("(B)", "B"),
    ("The answer is B.", "B"),
    ("Answer: **B**", "B"),
    ("Final answer: C", "C"),
    ("After thinking I think B is correct.", "B"),
    ("", None),
])
def test_mcq_letter_extraction(response, expected):
    assert extract_letter(response, ["a", "b", "c", "d"]) == expected


def test_mcq_grader_ok_path():
    item = {
        "id": "x_v1", "category": "fs_concepts",
        "grader": {"kind": "mcq", "config": {"choices": ["a", "b", "c", "d"]}},
        "golden": {"answer": "B"},
    }
    g = grade_mcq(item, "The answer is B.")
    assert g.ok and g.kind == "mcq"
    assert g.detail["predicted_letter"] == "B"


def test_mcq_grader_fail_path():
    item = {
        "id": "x_v1", "category": "fs_concepts",
        "grader": {"kind": "mcq", "config": {"choices": ["a", "b", "c", "d"]}},
        "golden": {"answer": "A"},
    }
    g = grade_mcq(item, "Definitely C.")
    assert not g.ok


# ----- trace_match -------------------------------------------------------

def test_trace_match_extract_from_fenced_json():
    response = """Sure, here's the trace:
    ```json
    [
      {"op": "write", "path": "/tool/find/ctl", "data": "*.b /appl"},
      {"op": "read",  "path": "/tool/find/ctl"}
    ]
    ```
    """
    trace = extract_trace(response)
    assert len(trace) == 2
    assert trace[0]["op"] == "write"
    assert trace[0]["path"] == "/tool/find/ctl"


def test_trace_match_grader_ok():
    item = {
        "id": "tool_invoke_find_v1", "category": "9p_tool_use",
        "grader": {"kind": "trace_match", "config": {"max_edit_distance": 0}},
        "golden": {"trace": [
            {"op": "write", "path": "/tool/find/ctl", "data": "*.b /appl"},
            {"op": "read",  "path": "/tool/find/ctl"},
        ]},
    }
    response = """```trace
[{"op":"write","path":"/tool/find/ctl","data":"*.b /appl"},
 {"op":"read","path":"/tool/find/ctl"}]
```"""
    g = grade_trace_match(item, response)
    assert g.ok
    assert g.detail["distance"] == 0


def test_trace_match_grader_needs_golden_when_absent():
    item = {
        "id": "tool_x_v1", "category": "9p_tool_use",
        "grader": {"kind": "trace_match", "config": {}},
        "needs_golden": True,
    }
    g = grade_trace_match(item, "anything")
    assert not g.ok
    assert "needs_golden" in g.detail.get("reason", "")


def test_trace_match_extract_limbo_open_bind():
    """IOL-35: idiomatic Limbo binds path on `open()` and uses fd later.
    The extractor must follow the binding and emit read/write against the
    bound path even when read/write themselves don't carry the path."""
    response = """```limbo
fd := sys->open("/tool/find/ctl", Sys->ORDWR);
args := "*.b /appl/veltro";
sys->fprint(fd, "%s", args);
sys->read(fd, buf, len buf);
```"""
    trace = extract_trace(response)
    ops = [(t["op"], t["path"]) for t in trace]
    assert ("write", "/tool/find/ctl") in ops
    assert ("read",  "/tool/find/ctl") in ops
    # data field should pick up the string-literal var
    writes = [t for t in trace if t["op"] == "write"]
    assert writes and writes[0].get("data") == "*.b /appl/veltro"


def test_trace_match_extract_skips_error_string_paths():
    """IOL-36: paths inside string literals (notably error printfs) must
    not be scored as real I/O ops."""
    response = '''sys->fprint(sys->fildes(2), "cannot read /tool/find/ctl: %r\\n");'''
    trace = extract_trace(response)
    assert trace == []


def test_trace_match_extract_fd_method_call():
    """Limbo Sys.FD method-call style: `fd.read(...)` / `fd.write(...)` —
    must be recognised the same as `sys->read(fd, ...)`."""
    response = """```limbo
fd := sys->open("/tool/_registry", Sys->OREAD);
n := fd.read(buf, len buf);
```"""
    ops = [(t["op"], t["path"]) for t in extract_trace(response)]
    assert ("read", "/tool/_registry") in ops


def test_trace_match_format_string_vs_data():
    """`sys->fprint(fd, "%s", args)` — the inline `"%s"` is the format,
    not the data. Data must come from the bareword `args` via the
    `args := "literal"` lookup."""
    response = """```limbo
fd := sys->open("/tool/find/ctl", Sys->ORDWR);
args := "*.b /appl";
sys->fprint(fd, "%s", args);
```"""
    trace = extract_trace(response)
    writes = [t for t in trace if t["op"] == "write"]
    assert writes and writes[0].get("data") == "*.b /appl"


def test_trace_match_inline_literal_as_data():
    """`sys->fprint(fd, "literal")` with no format specifier — the
    literal IS the data."""
    response = """```limbo
fd := sys->open("/tool/grep/ctl", Sys->OWRITE);
sys->fprint(fd, "implement\\n");
```"""
    trace = extract_trace(response)
    writes = [t for t in trace if t["op"] == "write"]
    assert writes and writes[0].get("data") == "implement\\n"


def test_trace_match_blanker_handles_apostrophe_in_comment():
    """IOL-39-adjacent regression: the string-literal blanker must NOT
    treat `'` as a delimiter. Comments like `# Veltro's tool` would
    otherwise blank everything from the apostrophe to EOF, killing the
    fd-binding scan downstream."""
    response = """```limbo
# Drive Veltro's find tool.
fd := sys->open("/tool/find/ctl", Sys->ORDWR);
sys->read(fd, buf, len buf);
```"""
    ops = [(t["op"], t["path"]) for t in extract_trace(response)]
    assert ("read", "/tool/find/ctl") in ops


def test_trace_match_data_wildcard_equivalence_class():
    """`equivalence_classes: [data_wildcard]` drops the data field
    before comparison — for items where the write payload is
    runtime-determined (argv, computed strings, etc.)."""
    item = {
        "id": "x_v1", "category": "9p_tool_use",
        "grader": {"kind": "trace_match", "config": {
            "max_edit_distance": 0,
            "equivalence_classes": ["data_wildcard"],
        }},
        "golden": {"trace": [
            {"op": "write", "path": "/tool/X/ctl", "data": "specific-payload"},
        ]},
    }
    # Response writes a runtime variable; extractor finds no inline literal.
    response = """```limbo
fd := sys->open("/tool/X/ctl", Sys->OWRITE);
sys->write(fd, buf, len buf);
```"""
    g = grade_trace_match(item, response)
    assert g.ok, f"data_wildcard should ignore data mismatch; got {g.detail}"


def test_trace_match_rc_redirect_still_works():
    """rc-style `echo X > /tool/Y/ctl` write + `cat /tool/Y/ctl` read."""
    response = "echo implement > /tool/grep/ctl\ncat /tool/grep/ctl\n"
    ops = [(t["op"], t["path"]) for t in extract_trace(response)]
    assert ("write", "/tool/grep/ctl") in ops
    assert ("read",  "/tool/grep/ctl") in ops


def test_edit_distance_basic():
    a = [{"op": "write", "path": "/tool/find/ctl", "data": "x"}]
    b = [{"op": "write", "path": "/tool/find/ctl", "data": "x"}]
    assert edit_distance(a, b) == 0
    assert edit_distance(a, []) == 1
    assert edit_distance([], b) == 1


# ----- dispatch ----------------------------------------------------------

def test_dispatch_dispatches_to_mcq():
    item = {
        "id": "x_v1", "category": "fs_concepts",
        "grader": {"kind": "mcq", "config": {"choices": ["a", "b"]}},
        "golden": {"answer": "A"},
    }
    g = grade(item, "Answer: A")
    assert g.kind == "mcq" and g.ok


def test_dispatch_unknown_kind_raises():
    item = {"id": "x_v1", "category": "fs_concepts",
            "grader": {"kind": "doesnt_exist"}}
    with pytest.raises(ValueError):
        grade(item, "anything")
