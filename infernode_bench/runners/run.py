"""Runner — call a chat-completion endpoint for each item, grade, emit JSONL.

Mirrors `infernode-os-llm/eval/compile_pass.py` in shape and defaults, so a
user moving from IOL's `make eval-baseline` to InferBench's smoke subset
sees identical knobs (`--model`, `--base-url`, `--temperature`, etc.).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import request

from infernode_bench.graders import grade
from infernode_bench.items import REPO_ROOT
from infernode_bench.subset import load_subset, resolve_subset, resolved_hash

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert programmer for the Inferno operating system "
    "(Limbo, Plan 9 idiom C, Inferno sh, 9P-native tool use). When asked "
    "for code, respond with one complete, compilable source file inside a "
    "single fenced code block tagged for the appropriate language. Do not "
    "add explanation outside the code fence."
)


def _chat_completion(base_url: str, model: str, system: str, user: str, *,
                     temperature: float, max_tokens: int, timeout_s: float,
                     num_ctx: int) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "options": {"num_ctx": num_ctx},   # Ollama-specific; ignored elsewhere
    }
    headers = {"Content-Type": "application/json"}
    if os.environ.get("OPENAI_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENAI_API_KEY']}"
    req = request.Request(url, data=json.dumps(payload).encode(),
                          method="POST", headers=headers)
    with request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read())


def _bench_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def run_subset(
    subset_name: str,
    *,
    model: str,
    base_url: str,
    out_dir: Path,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    num_ctx: int = 8192,
    timeout_s: float = 600.0,
    dry_run: bool = False,
    skip_needs_golden: bool = True,
) -> dict:
    subset = load_subset(subset_name)
    items = resolve_subset(subset)
    sub_hash = resolved_hash(items)

    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_model = re.sub(r"[^A-Za-z0-9._-]", "_", model)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_path = out_dir / f"{run_id}_{subset_name}_{safe_model}.jsonl"

    bench_sha = _bench_sha()
    print(
        f"model={model}  base_url={base_url}  subset={subset_name}  "
        f"items={len(items)}  hash={sub_hash[:12]}  bench_sha={bench_sha[:12]}",
        file=sys.stderr,
    )

    n_pass = 0
    n_graded = 0
    n_skipped = 0
    with run_path.open("w") as f_out:
        for item in items:
            sid = item["id"]
            if skip_needs_golden and item.get("needs_golden"):
                n_skipped += 1
                print(f"  {sid}: SKIP (needs_golden)", file=sys.stderr)
                row = {
                    "item_id": sid,
                    "category": item["category"],
                    "difficulty": item.get("difficulty"),
                    "model": model,
                    "ok": None,
                    "grader_kind": item["grader"]["kind"],
                    "grader_detail": {"skipped": "needs_golden"},
                    "run_id": run_id,
                    "bench_sha": bench_sha,
                    "subset_name": subset_name,
                    "subset_hash": sub_hash,
                    "timestamp": dt.datetime.utcnow().isoformat() + "Z",
                }
                f_out.write(json.dumps(row) + "\n")
                f_out.flush()
                continue

            t0 = time.monotonic()
            if dry_run:
                completion = "```limbo\nimplement Snippet;\n```"
            else:
                try:
                    resp = _chat_completion(
                        base_url, model, system_prompt, item["prompt"],
                        temperature=temperature, max_tokens=max_tokens,
                        timeout_s=timeout_s, num_ctx=num_ctx,
                    )
                    completion = resp["choices"][0]["message"]["content"]
                except Exception as e:
                    completion = ""
                    print(f"  {sid}: chat error: {e}", file=sys.stderr)
            chat_ms = int((time.monotonic() - t0) * 1000)

            try:
                gr = grade(item, completion)
            except Exception as e:
                print(f"  {sid}: GRADER ERROR — {e}", file=sys.stderr)
                gr_row = {"ok": False, "grader_kind": item["grader"]["kind"],
                          "grader_detail": {"error": str(e)},
                          "score": None, "grade_elapsed_ms": 0}
            else:
                gr_row = {
                    "ok": gr.ok,
                    "score": gr.score,
                    "grader_kind": gr.kind,
                    "grader_detail": gr.detail,
                    "grade_elapsed_ms": gr.elapsed_ms,
                }
                n_graded += 1
                if gr.ok:
                    n_pass += 1

            row = {
                "item_id": sid,
                "category": item["category"],
                "difficulty": item.get("difficulty"),
                "model": model,
                "endpoint": base_url,
                "completion": completion[:4000],   # cap for storage
                "completion_chars": len(completion),
                "chat_elapsed_ms": chat_ms,
                "run_id": run_id,
                "bench_sha": bench_sha,
                "subset_name": subset_name,
                "subset_hash": sub_hash,
                "timestamp": dt.datetime.utcnow().isoformat() + "Z",
                **gr_row,
            }
            f_out.write(json.dumps(row) + "\n")
            f_out.flush()
            verdict = "PASS" if gr_row.get("ok") else "FAIL"
            print(f"  {sid}: {verdict}  ({chat_ms}ms)", file=sys.stderr)

    summary = {
        "run_id": run_id,
        "subset": subset_name,
        "subset_hash": sub_hash,
        "model": model,
        "n_items": len(items),
        "n_graded": n_graded,
        "n_pass": n_pass,
        "n_skipped": n_skipped,
        "pass_rate": (n_pass / n_graded) if n_graded else None,
        "out_path": str(run_path),
        "bench_sha": bench_sha,
    }
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return summary
