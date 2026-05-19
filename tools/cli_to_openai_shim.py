#!/usr/bin/env python3
"""HTTP shim: serve `/v1/chat/completions` by invoking a frontier
CLI under the hood. Lets InferBench (or any OpenAI-compatible client)
benchmark models you have an interactive CLI for — e.g. Claude Code
(`claude -p`) under a subscription — without provisioning an API key.

Currently wraps the Claude Code CLI (`claude`). Adding another CLI
provider is a matter of writing a new `_call_*` function.

Usage:
    python tools/cli_to_openai_shim.py --port 11500 --cli claude

Then point InferBench at it:
    python -m infernode_bench run mini \\
        --model opus \\
        --base-url http://127.0.0.1:11500/v1 \\
        --temperature 0.0 ...

The `--model` is passed through to the CLI's `--model` flag verbatim.
The `system` and `user` messages from the request are mapped to
`--system-prompt` and the prompt positional arg respectively. Tool
calls / streaming / function calling are NOT supported — this is a
one-shot completion adapter for benchmarking.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import shutil
import subprocess
import logging
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

logger = logging.getLogger("cli-shim")


# --- claude (Claude Code) backend --------------------------------------

# Tools we want disabled when claude is being used as a completion engine.
# Without these the model may try to spawn its tool framework on every
# benchmark item, which makes the call slow, expensive, and non-deterministic.
_CLAUDE_DISABLED_TOOLS = [
    "Bash", "Edit", "Write", "Read", "Grep", "Glob",
    "WebSearch", "WebFetch", "TaskCreate", "TaskUpdate",
    "TaskList", "Agent",
]


def _call_claude(model: str, system: str, user: str, *,
                 timeout_s: float, max_tokens: int | None) -> dict:
    """Call `claude -p` and return an OpenAI-shaped response dict."""
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--permission-mode", "default",
        "--disallowed-tools", *_CLAUDE_DISABLED_TOOLS,
        # Move per-machine sections (cwd, env info, memory paths, git
        # status) out of the system prompt so prompt-cache hits across
        # benchmark items. Substantially reduces cache_creation tokens.
        "--exclude-dynamic-system-prompt-sections",
    ]
    if system:
        cmd += ["--system-prompt", system]
    # The user prompt is passed on stdin so it can contain newlines, quotes,
    # and arbitrary length without shell-escaping headaches.
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, input=user, capture_output=True, text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return _err_response(model, "timeout")
    elapsed = time.monotonic() - t0
    if proc.returncode != 0:
        return _err_response(model, f"claude exited {proc.returncode}: "
                                    f"{proc.stderr.strip()[:200]}")
    try:
        cli = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return _err_response(model, f"claude returned non-JSON: {e}")
    if cli.get("is_error"):
        return _err_response(model,
            f"claude error: {cli.get('result') or cli.get('api_error_status')}")
    content = cli.get("result") or ""
    usage = cli.get("usage") or {}
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": _map_finish(cli.get("stop_reason")),
        }],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": 0,  # filled below
        },
        "_x_cli_elapsed_s": elapsed,
        "_x_cli_cost_usd": cli.get("total_cost_usd"),
    }


def _map_finish(stop_reason: str | None) -> str:
    if stop_reason in (None, "end_turn", "stop_sequence"):
        return "stop"
    if stop_reason == "max_tokens":
        return "length"
    return stop_reason


def _err_response(model: str, msg: str) -> dict:
    return {
        "id": f"chatcmpl-err-{uuid.uuid4().hex[:16]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": ""},
            "finish_reason": "error",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "_x_cli_error": msg,
    }


_BACKENDS = {"claude": _call_claude}


# --- HTTP server -------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    server_version = "cli-shim/0.1"
    cli_backend = "claude"  # set on the server instance below

    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)

    def do_POST(self):
        if not self.path.startswith("/v1/chat/completions"):
            self.send_error(404, "only POST /v1/chat/completions")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body_bytes = self.rfile.read(length)
        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            self.send_error(400, "invalid JSON body")
            return
        model = payload.get("model") or "sonnet"
        messages = payload.get("messages") or []
        system = ""
        user = ""
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            elif m.get("role") == "user":
                user = m.get("content", "")
        max_tokens = payload.get("max_tokens")
        # InferBench's runner sets timeout_s on the request; we honour
        # the same value. Default to 600s if not specified.
        timeout_s = float(payload.get("timeout", 600.0))

        backend = _BACKENDS.get(self.cli_backend)
        if backend is None:
            self.send_error(500, f"unknown backend: {self.cli_backend}")
            return
        resp = backend(model, system, user,
                       timeout_s=timeout_s, max_tokens=max_tokens)
        if "usage" in resp:
            u = resp["usage"]
            u["total_tokens"] = u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
        body = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=11500)
    p.add_argument("--cli", choices=list(_BACKENDS), default="claude")
    p.add_argument("--log", default="INFO")
    args = p.parse_args()
    logging.basicConfig(level=args.log, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if shutil.which("claude") is None and args.cli == "claude":
        sys.exit("`claude` not found on PATH")
    _Handler.cli_backend = args.cli
    server = HTTPServer(("127.0.0.1", args.port), _Handler)
    logger.info(f"cli-shim listening on http://127.0.0.1:{args.port}/v1/  "
                f"(backend: {args.cli})")
    server.serve_forever()


if __name__ == "__main__":
    main()
