"""Compile-gate adapter — delegates to infernode-os-llm's local gate.

Per IB-7: the compile gate lives in `infernode-os-llm/tools/compile_gate/`
and is load-bearing for IOL itself; the bench repo MUST NOT duplicate it.

Two backends are supported here, picked per `INFERBENCH_GATE_BACKEND`:

    subprocess (default)  — set INFERNODE_OS_LLM to a checkout path; we
                            shell out to its local.sh, picking up the
                            native limbo + emu binaries from the
                            submodule.
    docker                — `docker run --rm -i $INFERBENCH_GATE_IMAGE`.
                            Image must already exist locally (or be
                            pullable). IOL is on the hook for publishing
                            a tagged image (linked IOL ticket).

The HTTP option from the epic is not implemented in v0.

Output `detail` includes everything the gate emits plus the InferNode
submodule SHA in use (so leaderboard rows pin against gate semantics).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from infernode_bench.graders import GradeResult

GATE_LANG_BY_LANGUAGE = {"limbo": "limbo", "c": "c", "inferno_sh": "rc"}

CODE_FENCE_RE = re.compile(
    r"```(?:limbo|b|c|sh|rc|inferno_sh|inferno-sh|9p|plan9|plan9-c)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


class GateUnavailable(RuntimeError):
    pass


def _extract_code(response: str) -> str:
    """Pull the most-likely-code block out of the model's reply.

    Mirrors infernode-os-llm/eval/compile_pass.py:extract_code — pick the
    longest fenced block; fall back to whole response trimmed to the
    first `implement` if present.
    """
    matches = list(CODE_FENCE_RE.finditer(response))
    if matches:
        return max((m.group(1) for m in matches), key=len).strip("\n")
    impl = response.find("implement ")
    return response[impl:] if impl >= 0 else response


def _resolve_iol_root() -> Path:
    env = os.environ.get("INFERNODE_OS_LLM")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "tools" / "compile_gate" / "local.sh").is_file():
            return p
        raise GateUnavailable(
            f"INFERNODE_OS_LLM={env!r} does not look like an infernode-os-llm checkout "
            f"(missing tools/compile_gate/local.sh)."
        )
    # Best-effort co-located checkout discovery — useful in dev where
    # both repos sit side-by-side.
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "infernode-os-llm"
        if (cand / "tools" / "compile_gate" / "local.sh").is_file():
            return cand
    raise GateUnavailable(
        "INFERNODE_OS_LLM env var is unset and no co-located checkout found. "
        "Set INFERNODE_OS_LLM=/path/to/infernode-os-llm or use --backend docker."
    )


def _infernode_sha(iol_root: Path) -> str | None:
    sub = iol_root / "infernode"
    if not sub.is_dir():
        return None
    try:
        return subprocess.check_output(
            ["git", "-C", str(sub), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _run_subprocess(source: str, gate_lang: str, timeout_s: float) -> dict:
    iol_root = _resolve_iol_root()
    gate = iol_root / "tools" / "compile_gate" / "local.sh"
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
        result = json.loads(line)
    except (IndexError, ValueError):
        result = {
            "ok": False,
            "stderr": (
                f"gate emitted no JSON. exit={proc.returncode} "
                f"stderr={proc.stderr.decode(errors='replace')[:500]}"
            ),
            "dis_size": None,
            "backend": "subprocess-broken",
            "elapsed_ms": 0,
            "wrapped": False,
        }
    result["infernode_sha"] = _infernode_sha(iol_root)
    return result


def _run_docker(source: str, gate_lang: str, timeout_s: float) -> dict:
    image = os.environ.get("INFERBENCH_GATE_IMAGE", "infernode-os-llm/compile-gate:latest")
    if shutil.which("docker") is None:
        raise GateUnavailable("docker backend selected but `docker` not on PATH")
    proc = subprocess.run(
        ["docker", "run", "--rm", "-i", "-e", f"GATE_LANG={gate_lang}", image],
        input=source.encode(),
        capture_output=True,
        timeout=timeout_s,
    )
    try:
        line = proc.stdout.decode().strip().splitlines()[-1]
        return json.loads(line)
    except (IndexError, ValueError):
        return {
            "ok": False,
            "stderr": (
                f"docker gate emitted no JSON. exit={proc.returncode} "
                f"stderr={proc.stderr.decode(errors='replace')[:500]}"
            ),
            "dis_size": None,
            "backend": "docker-broken",
            "elapsed_ms": 0,
            "wrapped": False,
        }


def grade_compile_gate(item: dict, response: str) -> GradeResult:
    cfg = item["grader"]["config"]
    gate_lang = cfg["gate_lang"]
    timeout_s = float(os.environ.get("INFERBENCH_GATE_TIMEOUT_S", "30"))
    backend = os.environ.get("INFERBENCH_GATE_BACKEND", "subprocess")

    code = _extract_code(response) if response else ""
    if not code:
        return GradeResult(
            ok=False, kind="compile_gate",
            detail={"reason": "no code extracted", "backend": backend,
                    "gate_lang": gate_lang},
        )

    t0 = time.monotonic()
    if backend == "docker":
        result = _run_docker(code, gate_lang, timeout_s)
    else:
        result = _run_subprocess(code, gate_lang, timeout_s)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    ok = bool(result.get("ok"))
    detail = {
        "gate_lang": gate_lang,
        "backend": result.get("backend", backend),
        "dis_size": result.get("dis_size"),
        "wrapped": result.get("wrapped"),
        "stderr_tail": (result.get("stderr") or "")[-500:],
        "infernode_sha": result.get("infernode_sha"),
        "code_chars": len(code),
    }
    return GradeResult(ok=ok, kind="compile_gate", detail=detail, elapsed_ms=elapsed_ms)
