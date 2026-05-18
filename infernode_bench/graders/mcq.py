"""MCQ grader — exact match on the predicted letter.

Per IB-10. Handles the top model output formats:

    "B"
    "(B)"
    "B."
    "The answer is B."
    "I think the answer is **B**."
    "Answer: B"

Strategy: scan for the first standalone uppercase letter in {A..H} that
isn't preceded by another letter. Letters wrapped in parens or markdown
bold are unwrapped first.
"""

from __future__ import annotations

import re
import time

from infernode_bench.graders import GradeResult

# Strip wrapping characters that commonly surround the letter.
_LETTER_CTX = re.compile(
    r"(?<![A-Za-z])([A-H])(?![A-Za-z])"
)


def extract_letter(response: str, choices: list[str]) -> str | None:
    """Return the first plausible letter from the response, or None."""
    if not response:
        return None
    valid = {chr(ord("A") + i) for i in range(len(choices))}
    # First, look for "answer is X" / "Answer: X" — strongest signal.
    m = re.search(
        r"(?:final\s+answer|answer)\s*(?:is|:)\s*\*?\*?\(?\s*([A-H])\b",
        response,
        re.IGNORECASE,
    )
    if m and m.group(1) in valid:
        return m.group(1)
    # Otherwise: first matching standalone letter.
    for m in _LETTER_CTX.finditer(response):
        if m.group(1) in valid:
            return m.group(1)
    return None


def grade_mcq(item: dict, response: str) -> GradeResult:
    t0 = time.monotonic()
    cfg = item["grader"]["config"]
    choices = cfg["choices"]
    expected = (item.get("golden") or {}).get("answer", "").upper().strip()
    predicted = extract_letter(response or "", choices)
    ok = predicted is not None and predicted == expected
    return GradeResult(
        ok=bool(ok),
        kind="mcq",
        detail={
            "predicted_letter": predicted,
            "expected_letter": expected or None,
            "n_choices": len(choices),
        },
        elapsed_ms=int((time.monotonic() - t0) * 1000),
    )
