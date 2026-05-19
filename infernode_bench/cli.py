"""`python -m infernode_bench …` — surface for listing items, resolving
subsets, validating, and running an eval.

Subcommands:

    list                   item counts by category
    list items [cat]       per-item summary (id, category, difficulty, needs_golden)
    subset resolve <name>  print the deterministic ID list + resolved hash
    subset hashes          print the resolved hash for every subset file
    validate               schema-check every item; non-zero exit on any failure
    verify [--strict]      gate-validate every item's golden against its grader
    run <subset>           call the model, grade, emit JSONL
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from infernode_bench import (
    CATEGORIES,
    REPO_ROOT,
    load_items,
    load_subset,
    resolve_subset,
)
from infernode_bench.schema import iter_item_errors
from infernode_bench.subset import resolved_hash


def _cmd_list(args: argparse.Namespace) -> int:
    if args.what == "items":
        items = load_items(category=args.category)
        for it in sorted(items, key=lambda x: (x["category"], x["id"])):
            flag = "NG " if it.get("needs_golden") else "   "
            print(f"  {flag}{it['category']:18s}  {it['difficulty']:8s}  {it['id']}")
        print(f"\ntotal: {len(items)} items", file=sys.stderr)
        return 0

    # default: counts
    items = load_items()
    by_cat = Counter(it["category"] for it in items)
    by_diff = Counter((it["category"], it["difficulty"]) for it in items)
    needs_golden = sum(1 for it in items if it.get("needs_golden"))
    print(f"InferBench item set under {REPO_ROOT / 'items'}\n")
    print(f"{'category':<20s} {'count':>6s}  difficulty distribution")
    print(f"{'-' * 20} {'-' * 6}  {'-' * 40}")
    for cat in CATEGORIES:
        n = by_cat.get(cat, 0)
        dist = ", ".join(
            f"{d}={by_diff.get((cat, d), 0)}"
            for d in ("trivial", "easy", "medium", "hard")
            if by_diff.get((cat, d), 0) > 0
        )
        print(f"{cat:<20s} {n:>6d}  {dist}")
    print()
    print(f"total: {len(items)} items, {needs_golden} pending goldens")
    return 0


def _cmd_subset(args: argparse.Namespace) -> int:
    if args.action == "resolve":
        subset = load_subset(args.name)
        items = resolve_subset(subset)
        h = resolved_hash(items)
        print(f"# subset={args.name}  seed={subset['seed']}  n={len(items)}  hash={h}")
        for it in items:
            print(it["id"])
        return 0
    if args.action == "hashes":
        from infernode_bench.subset import SUBSETS_DIR
        for path in sorted(SUBSETS_DIR.glob("*.yaml")):
            name = path.stem
            try:
                subset = load_subset(name)
                items = resolve_subset(subset)
                h = resolved_hash(items)
                print(f"{name:<10s}  {len(items):>4d} items  {h}")
            except Exception as e:
                print(f"{name:<10s}  ERROR: {e}")
        return 0
    raise SystemExit(f"unknown subset action: {args.action!r}")


def _cmd_validate(args: argparse.Namespace) -> int:
    items = load_items(category=args.category, include_deprecated=True)
    ids = [it["id"] for it in items]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    n_err = 0
    for it in items:
        errors = list(iter_item_errors(it))
        if errors:
            n_err += 1
            print(f"  {it.get('id', '<missing>')}: {len(errors)} error(s)")
            for e in errors:
                path = ".".join(str(p) for p in e.absolute_path) or "<root>"
                print(f"     {path}: {e.message}")
    if dup:
        n_err += len(dup)
        print(f"  duplicate ids: {dup}")
    if n_err:
        print(f"\n{n_err} problem(s) across {len(items)} items", file=sys.stderr)
        return 1
    n_ng = sum(1 for it in items if it.get("needs_golden"))
    print(f"OK — {len(items)} items pass schema validation ({n_ng} need goldens)",
          file=sys.stderr)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from infernode_bench.verify import main as verify_main
    argv = []
    if args.category:
        argv += ["--category", args.category]
    if args.strict:
        argv.append("--strict")
    if args.quiet:
        argv.append("--quiet")
    if args.json:
        argv.append("--json")
    return verify_main(argv)


def _cmd_calibration(args: argparse.Namespace) -> int:
    from infernode_bench.calibration import main as calib_main
    return calib_main(args.calib_args)


def _cmd_run(args: argparse.Namespace) -> int:
    from infernode_bench.runners import run_subset
    think = None
    if args.no_think:
        think = False
    elif args.think:
        think = True
    summary = run_subset(
        args.subset,
        model=args.model,
        base_url=args.base_url,
        out_dir=Path(args.out_dir),
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        num_ctx=args.num_ctx,
        timeout_s=args.timeout,
        dry_run=args.dry_run,
        skip_needs_golden=not args.include_needs_golden,
        think=think,
    )
    return 0 if summary["n_graded"] > 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="infernode-bench", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="list categories / items")
    pl.add_argument("what", nargs="?", default="categories",
                    choices=["categories", "items"])
    pl.add_argument("category", nargs="?", default=None,
                    help="restrict to one category (with `items`)")
    pl.set_defaults(func=_cmd_list)

    ps = sub.add_parser("subset", help="subset operations")
    ps.add_argument("action", choices=["resolve", "hashes"])
    ps.add_argument("name", nargs="?", default=None,
                    help="subset name (required for `resolve`)")
    ps.set_defaults(func=_cmd_subset)

    pv = sub.add_parser("validate", help="schema-validate every item")
    pv.add_argument("--category", default=None)
    pv.set_defaults(func=_cmd_validate)

    pvf = sub.add_parser("verify", help="gate-validate every item's golden")
    pvf.add_argument("--category", default=None)
    pvf.add_argument("--strict", action="store_true",
                     help="fail on any needs_golden SKIP too")
    pvf.add_argument("--quiet", action="store_true")
    pvf.add_argument("--json", action="store_true",
                     help="emit one JSON line per item")
    pvf.set_defaults(func=_cmd_verify)

    pc = sub.add_parser("calibration", help="Phase-0 calibration set operations")
    pc.add_argument("calib_args", nargs=argparse.REMAINDER)
    pc.set_defaults(func=_cmd_calibration)

    pr = sub.add_parser("run", help="run a subset against a model")
    pr.add_argument("subset", help="subset name (smoke, mini, full, ...)")
    pr.add_argument("--model", required=True)
    pr.add_argument("--base-url", default="http://localhost:11434/v1")
    pr.add_argument("--out-dir", default=str(REPO_ROOT / "runs"))
    pr.add_argument("--temperature", type=float, default=0.0)
    pr.add_argument("--max-tokens", type=int, default=None,
                    help="override per-item max-token cap; default is "
                         "per-language (Limbo 1500, others 800)")
    pr.add_argument("--num-ctx", type=int, default=8192)
    pr.add_argument("--timeout", type=float, default=600.0)
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--include-needs-golden", action="store_true",
                    help="include items lacking goldens (will return needs_golden detail)")
    pr.add_argument("--no-think", action="store_true",
                    help="disable thinking-mode (Qwen3, gpt-oss, etc.) — "
                         "switches to Ollama's native /api/chat with "
                         "think=false. Use this when a model's visible "
                         "response is empty because all tokens went to the "
                         "hidden reasoning channel.")
    pr.add_argument("--think", action="store_true",
                    help="explicitly enable thinking-mode via Ollama's "
                         "/api/chat. Default for thinking models is "
                         "Ollama's per-model setting.")
    pr.set_defaults(func=_cmd_run)

    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "subset" and args.action == "resolve" and not args.name:
        print("error: `subset resolve` requires a name", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
