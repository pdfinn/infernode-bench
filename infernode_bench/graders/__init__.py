"""Graders.

Each grader takes (item, model_response) and returns a `GradeResult`:

    @dataclass
    class GradeResult:
        ok: bool
        score: float | None
        detail: dict
        kind: str           # echoed item.grader.kind
        elapsed_ms: int

The runner dispatches by `item['grader']['kind']`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class GradeResult:
    ok: bool
    kind: str
    score: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def grade(item: dict, response: str) -> GradeResult:
    """Dispatch by grader.kind. Lazy-imports each backend so callers that
    only need MCQ don't pay for the compile-gate adapter's subprocess
    setup, etc."""
    kind = item["grader"]["kind"]
    if kind == "compile_gate":
        from infernode_bench.graders.compile_gate import grade_compile_gate
        return grade_compile_gate(item, response)
    if kind == "mcq":
        from infernode_bench.graders.mcq import grade_mcq
        return grade_mcq(item, response)
    if kind == "trace_match":
        from infernode_bench.graders.trace_match import grade_trace_match
        return grade_trace_match(item, response)
    if kind == "judge":
        from infernode_bench.graders.judge import grade_judge
        return grade_judge(item, response)
    raise ValueError(f"unknown grader kind: {kind!r}")
