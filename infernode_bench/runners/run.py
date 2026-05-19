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

# Per-language max_tokens defaults (IOL-32). Limbo programs are wordy
# (module decl + includes + ADT decls + init body); 800 tokens was tight
# in the v4-e1 smoke run and clipped ≥4 items mid-construct, causing
# bogus syntax-error grades. Other languages stay at the older default.
_MAX_TOKENS_PER_LANGUAGE: dict[str, int] = {
    "limbo": 1500,
}
_MAX_TOKENS_FALLBACK = 800


def _max_tokens_for(item: dict, explicit: int | None) -> int:
    """Resolve max_tokens for one item.

    - If the CLI passed an explicit `--max-tokens`, that wins.
    - Otherwise fall back to the per-language default, then to a generic
      cap. The `language` field on the item is authoritative; categories
      like `9p_tool_use` whose response *language* is Limbo use the Limbo
      cap correctly.
    """
    if explicit is not None:
        return explicit
    return _MAX_TOKENS_PER_LANGUAGE.get(
        (item.get("language") or "").lower(), _MAX_TOKENS_FALLBACK,
    )


def _looks_truncated(completion: str, item: dict) -> bool:
    """Heuristic: did the model run out of tokens mid-response?

    Triggers if either:
      - the completion ends inside an unclosed fenced code block, OR
      - the last non-empty source line is mid-expression (no terminator
        and no closing brace), suggesting clipped output rather than a
        natural stop.

    Used only to *flag* a row (`truncated: true`); doesn't change the
    grade verdict.
    """
    if not completion:
        return False
    # Unclosed fenced block: odd number of ``` fences
    if completion.count("```") % 2 == 1:
        return True
    tail = completion.rstrip()
    if not tail:
        return False
    last_line = tail.splitlines()[-1].rstrip()
    if not last_line:
        return False
    if last_line.endswith(("```", "}", ";", ")", "]", "'", '"')):
        return False
    # Limbo / C / sh statements normally close with one of the chars
    # above. Anything else at the very end of the response is suspicious.
    return True


def _chat_completion(base_url: str, model: str, system: str, user: str, *,
                     temperature: float, max_tokens: int, timeout_s: float,
                     num_ctx: int, think: bool | None = None) -> dict[str, Any]:
    """Issue a chat-completion request. Two endpoints supported:

    - ``base_url`` ending in ``/v1`` (OpenAI-compatible) — used for
      anything that speaks the OpenAI Chat Completions protocol
      (Ollama's compat layer, the CLI shim, real OpenAI/Anthropic
      APIs).
    - ``base_url`` ending in ``/api`` — Ollama's native chat endpoint.
      This path is required when ``think=False`` because Ollama's
      OpenAI-compatibility layer doesn't honour the ``think`` flag,
      and thinking-capable models (Qwen3, gpt-oss, …) otherwise
      spend the whole token budget on hidden reasoning and return an
      empty visible response.

    Returns a dict whose ``choices[0].message.content`` is the visible
    response and whose top-level shape is OpenAI-compatible (so the
    runner doesn't care which endpoint was used).
    """
    is_ollama_native = base_url.rstrip("/").endswith("/api")
    if is_ollama_native or think is not None:
        # Use Ollama's native /api/chat. Honours `think` properly.
        url = base_url.rstrip("/") + ("/chat" if is_ollama_native else "")
        if not url.endswith("/chat"):
            # base_url is /v1; rewrite to /api for the think path.
            url = base_url.rstrip("/").rsplit("/", 1)[0] + "/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": num_ctx,
            },
        }
        if think is not None:
            payload["think"] = think
        headers = {"Content-Type": "application/json"}
        req = request.Request(url, data=json.dumps(payload).encode(),
                              method="POST", headers=headers)
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read())
        # Translate Ollama's /api/chat response into OpenAI shape so the
        # caller doesn't need to special-case.
        content = (raw.get("message") or {}).get("content", "")
        done_reason = raw.get("done_reason") or "stop"
        return {
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "length" if done_reason == "length" else "stop",
            }],
            "usage": {
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
            },
        }

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
    max_tokens: int | None = None,
    num_ctx: int = 8192,
    timeout_s: float = 600.0,
    dry_run: bool = False,
    skip_needs_golden: bool = True,
    think: bool | None = None,
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

            item_max_tokens = _max_tokens_for(item, max_tokens)
            t0 = time.monotonic()
            if dry_run:
                completion = "```limbo\nimplement Snippet;\n```"
            else:
                try:
                    resp = _chat_completion(
                        base_url, model, system_prompt, item["prompt"],
                        temperature=temperature, max_tokens=item_max_tokens,
                        timeout_s=timeout_s, num_ctx=num_ctx, think=think,
                    )
                    completion = resp["choices"][0]["message"]["content"]
                except Exception as e:
                    completion = ""
                    print(f"  {sid}: chat error: {e}", file=sys.stderr)
            chat_ms = int((time.monotonic() - t0) * 1000)
            truncated = _looks_truncated(completion, item)

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
                "context_freshness": item.get("context_freshness") or "cold",
                "model": model,
                "endpoint": base_url,
                "completion": completion[:4000],   # cap for storage
                "completion_chars": len(completion),
                "chat_elapsed_ms": chat_ms,
                "max_tokens": item_max_tokens,
                "truncated": truncated,
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
