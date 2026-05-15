"""Phase-0 calibration set helpers (IB-2, IB-3).

The calibration set lives at `calibration/v0.yaml` outside the public
item tree — it's the empirical input to per-category sizing (IB-3), not
part of any leaderboard subset.

Surface:
    `python -m infernode_bench calibration verify`     gate-check goldens
    `python -m infernode_bench calibration list`       per-item summary
    `python -m infernode_bench calibration run ...`    grade against a model
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

from infernode_bench.graders import grade
from infernode_bench.items import REPO_ROOT
from infernode_bench.runners.run import (
    DEFAULT_SYSTEM_PROMPT,
    _bench_sha,
    _chat_completion,
)
from infernode_bench.schema import validate_item
from infernode_bench.verify import verify_one

CALIB_PATH = REPO_ROOT / "calibration" / "v0.yaml"


def load_calibration() -> list[dict]:
    with CALIB_PATH.open() as f:
        data = yaml.safe_load(f)
    items = list(data.get("items") or [])
    for item in items:
        validate_item(item)
    return items


def cmd_list(args) -> int:
    items = load_calibration()
    print(f"calibration set: {CALIB_PATH.relative_to(REPO_ROOT)}  ({len(items)} items)\n")
    for it in items:
        flags = []
        if it.get("needs_golden"):
            flags.append("needs_golden")
        if it.get("deprecated"):
            flags.append("deprecated")
        print(f"  {it['category']:18s} {it['difficulty']:8s} {it['id']:38s}"
              f"  {'+'.join(flags) or '-'}")
    return 0


def cmd_verify(args) -> int:
    items = load_calibration()
    n_pass = n_fail = n_skip = 0
    fails = []
    for it in items:
        v, d = verify_one(it)
        flag = {"PASS": "✓", "FAIL": "✗", "SKIP": "·"}[v]
        print(f"  {flag} {v:5s} {it['category']:18s} {it['id']:38s}  {d}")
        if v == "PASS":
            n_pass += 1
        elif v == "FAIL":
            n_fail += 1
            fails.append((it["id"], d))
        else:
            n_skip += 1
    print(f"\n{n_pass}/{len(items)} PASS  ({n_fail} FAIL, {n_skip} SKIP)",
          file=sys.stderr)
    return 0 if n_fail == 0 else 1


def cmd_run(args) -> int:
    items = load_calibration()
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_model = re.sub(r"[^A-Za-z0-9._-]", "_", args.model)
    out_dir = Path(args.out_dir or (REPO_ROOT / "runs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}_calibration_v0_{safe_model}.jsonl"

    bench_sha = _bench_sha()
    print(f"model={args.model}  base_url={args.base_url}  items={len(items)}  "
          f"bench_sha={bench_sha[:12]}", file=sys.stderr)

    n_pass = 0
    by_cat: dict[str, list[int]] = {}
    by_diff: dict[str, list[int]] = {}
    with out_path.open("w") as f_out:
        for item in items:
            sid = item["id"]
            try:
                resp = _chat_completion(
                    args.base_url, args.model,
                    DEFAULT_SYSTEM_PROMPT, item["prompt"],
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    timeout_s=args.timeout,
                    num_ctx=args.num_ctx,
                )
                completion = resp["choices"][0]["message"]["content"]
            except Exception as e:
                completion = ""
                print(f"  {sid}: chat error: {e}", file=sys.stderr)
            try:
                gr = grade(item, completion)
                ok = gr.ok
                detail = gr.detail
            except Exception as e:
                ok = False
                detail = {"error": str(e)}
            row = {
                "item_id": sid,
                "category": item["category"],
                "difficulty": item["difficulty"],
                "model": args.model,
                "ok": ok,
                "grader_kind": item["grader"]["kind"],
                "grader_detail": detail,
                "completion_chars": len(completion),
                "run_id": run_id,
                "bench_sha": bench_sha,
                "set": "calibration_v0",
            }
            f_out.write(json.dumps(row) + "\n")
            f_out.flush()
            by_cat.setdefault(item["category"], []).append(int(ok))
            by_diff.setdefault(item["difficulty"], []).append(int(ok))
            if ok:
                n_pass += 1
            print(f"  {'PASS' if ok else 'FAIL'}  {item['category']:18s} "
                  f"{item['difficulty']:8s} {sid}", file=sys.stderr)

    summary = {
        "run_id": run_id,
        "model": args.model,
        "n_items": len(items),
        "n_pass": n_pass,
        "by_category": {c: f"{sum(v)}/{len(v)}" for c, v in by_cat.items()},
        "by_difficulty": {d: f"{sum(v)}/{len(v)}" for d, v in by_diff.items()},
        "out_path": str(out_path),
        "bench_sha": bench_sha,
    }
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="infernode-bench calibration",
                                description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("verify").set_defaults(func=cmd_verify)

    pr = sub.add_parser("run")
    pr.add_argument("--model", required=True)
    pr.add_argument("--base-url", default="http://localhost:11434/v1")
    pr.add_argument("--out-dir", default=None)
    pr.add_argument("--temperature", type=float, default=0.0)
    pr.add_argument("--max-tokens", type=int, default=2048)
    pr.add_argument("--num-ctx", type=int, default=8192)
    pr.add_argument("--timeout", type=float, default=600.0)
    pr.set_defaults(func=cmd_run)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
