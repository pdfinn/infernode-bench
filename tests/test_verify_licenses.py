"""Tests for the verify module's pure-Python logic + the SPDX manifest.

The compile-gate-dependent verify path is exercised end-to-end via
`make verify` in CI; here we only test the parts that don't shell out.
"""


from infernode_bench.licenses import build_manifest, render_table
from infernode_bench.verify import verify_one


# ----- verify_one (no gate) ----------------------------------------------

def test_verify_one_skips_needs_golden():
    item = {"id": "x_v1", "category": "limbo_authoring", "needs_golden": True,
            "grader": {"kind": "compile_gate", "config": {"gate_lang": "limbo"}}}
    v, d = verify_one(item)
    assert v == "SKIP" and d == "needs_golden"


def test_verify_one_skips_deprecated():
    item = {"id": "x_v1", "category": "plan9_c", "deprecated": True,
            "grader": {"kind": "compile_gate", "config": {"gate_lang": "c"}}}
    v, d = verify_one(item)
    assert v == "SKIP"


def test_verify_one_trace_match_pass():
    item = {"id": "t_v1", "category": "9p_tool_use",
            "grader": {"kind": "trace_match", "config": {}},
            "golden": {"trace": [{"op": "write", "path": "/tool/find/ctl"},
                                 {"op": "read", "path": "/tool/find/ctl"}]}}
    v, d = verify_one(item)
    assert v == "PASS"


def test_verify_one_trace_match_bad_op():
    item = {"id": "t_v1", "category": "9p_tool_use",
            "grader": {"kind": "trace_match", "config": {}},
            "golden": {"trace": [{"op": "delete", "path": "/tool/x/ctl"}]}}
    v, d = verify_one(item)
    assert v == "FAIL"


def test_verify_one_mcq_pass():
    item = {"id": "m_v1", "category": "fs_concepts",
            "grader": {"kind": "mcq",
                       "config": {"choices": ["a", "b", "c", "d"]}},
            "golden": {"answer": "B"}}
    v, d = verify_one(item)
    assert v == "PASS"


def test_verify_one_mcq_out_of_range():
    item = {"id": "m_v1", "category": "fs_concepts",
            "grader": {"kind": "mcq",
                       "config": {"choices": ["a", "b"]}},
            "golden": {"answer": "C"}}
    v, d = verify_one(item)
    assert v == "FAIL"


def test_verify_one_judge_requires_exemplar():
    item = {"id": "j_v1", "category": "fs_concepts",
            "grader": {"kind": "judge", "config": {"criteria": ["accuracy"]}},
            "golden": {"exemplar": "the answer is X"}}
    assert verify_one(item)[0] == "PASS"

    item2 = {**item, "golden": {}}
    assert verify_one(item2)[0] == "FAIL"


# ----- licenses ----------------------------------------------------------

def test_manifest_aggregates_correctly():
    m = build_manifest()
    assert m["n_items"] >= 49
    assert sum(m["by_license"].values()) == m["n_items"]
    # Every checked-in baseline_v2 item is MIT.
    assert "MIT" in m["by_license"]


def test_render_table_has_header():
    m = build_manifest()
    t = render_table(m)
    assert "| License |" in t
    assert "MIT" in t
