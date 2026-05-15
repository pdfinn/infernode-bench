"""LLM-as-judge grader for open-ended `fs_concepts`.

Per IB-9. v0 implements the wire protocol against an OpenAI-compatible
chat completions endpoint. The validation study (50-item human-vs-judge,
κ ≥ 0.6) is a separate ticket (IB-17) and is NOT exercised here.

The judge prompt is intentionally simple and committed to the repo —
methodological changes to it must bump `JUDGE_PROMPT_VERSION` so result
rows are comparable across runs.
"""

from __future__ import annotations

import json
import os
import time
from urllib import request

from infernode_bench.graders import GradeResult

JUDGE_PROMPT_VERSION = "v0.1"

JUDGE_SYSTEM = (
    "You are a strict grader for an LLM benchmark on the Inferno operating "
    "system's filesystem and namespace concepts. Score the candidate "
    "response against the rubric — do NOT reward verbosity, do NOT reward "
    "phrasing similarity to the exemplar, and do NOT use the candidate's "
    "confidence as a signal. Return JSON only."
)

JUDGE_USER_TEMPLATE = """Item prompt:
---
{prompt}
---

Candidate response:
---
{response}
---

Exemplar response (for calibration only — do NOT require similarity):
---
{exemplar}
---

Score each criterion as 0 (fails) or 1 (meets). Return JSON of the form:

{{"criteria": {{"criterion_name": 0|1, ...}}, "rationale": "...", "ok": true|false}}

The overall `ok` is true iff ALL criteria score 1.

Criteria to score:
{criteria_list}
"""


def _call_judge(endpoint: str, judge_model: str, system: str, user: str,
                timeout_s: float = 120.0) -> str:
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = {
        "model": judge_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
    }
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if os.environ.get("OPENAI_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENAI_API_KEY']}"
    if os.environ.get("INFERBENCH_JUDGE_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['INFERBENCH_JUDGE_API_KEY']}"
    req = request.Request(url, data=body, method="POST", headers=headers)
    with request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def grade_judge(item: dict, response: str) -> GradeResult:
    t0 = time.monotonic()
    cfg = item["grader"]["config"]
    criteria = cfg["criteria"]
    judge_model = cfg.get("judge_model") or os.environ.get("INFERBENCH_JUDGE_MODEL")
    endpoint = os.environ.get("INFERBENCH_JUDGE_BASE_URL")
    if not judge_model or not endpoint:
        return GradeResult(
            ok=False, kind="judge",
            detail={
                "reason": "judge unavailable (set INFERBENCH_JUDGE_MODEL + "
                          "INFERBENCH_JUDGE_BASE_URL)",
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
            },
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )

    golden = item.get("golden") or {}
    exemplar = golden.get("exemplar", "")
    user = JUDGE_USER_TEMPLATE.format(
        prompt=item["prompt"],
        response=response or "",
        exemplar=exemplar,
        criteria_list="\n".join(f"  - {c}" for c in criteria),
    )
    try:
        raw = _call_judge(endpoint, judge_model, JUDGE_SYSTEM, user)
    except Exception as e:
        return GradeResult(
            ok=False, kind="judge",
            detail={"reason": f"judge call failed: {e}",
                    "judge_prompt_version": JUDGE_PROMPT_VERSION},
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )

    # Best-effort JSON extraction from the judge's reply.
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        verdict = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return GradeResult(
            ok=False, kind="judge",
            detail={"reason": "judge reply was not JSON",
                    "raw_head": (raw or "")[:500],
                    "judge_prompt_version": JUDGE_PROMPT_VERSION},
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )

    crit_scores = verdict.get("criteria") or {}
    ok = bool(verdict.get("ok")) and all(int(v) == 1 for v in crit_scores.values())
    score = (sum(int(v) for v in crit_scores.values()) / len(crit_scores)
             if crit_scores else None)
    return GradeResult(
        ok=ok, kind="judge", score=score,
        detail={
            "criteria": crit_scores,
            "rationale": verdict.get("rationale", "")[:500],
            "judge_model": judge_model,
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
        },
        elapsed_ms=int((time.monotonic() - t0) * 1000),
    )
