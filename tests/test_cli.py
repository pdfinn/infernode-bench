"""CLI smoke tests."""

import sys

import pytest

from infernode_bench.cli import build_parser, main


def _run(argv: list[str], capsys) -> int:
    sys_argv = sys.argv
    try:
        sys.argv = ["infernode-bench", *argv]
        return main()
    finally:
        sys.argv = sys_argv


def test_list_categories_returns_zero(capsys):
    assert _run(["list"], capsys) == 0


def test_validate_returns_zero(capsys):
    assert _run(["validate"], capsys) == 0


def test_subset_resolve_smoke(capsys):
    assert _run(["subset", "resolve", "smoke"], capsys) == 0
    out = capsys.readouterr().out
    assert "subset=smoke" in out
    assert "hello_world_v1" in out


def test_subset_hashes(capsys):
    assert _run(["subset", "hashes"], capsys) == 0


def test_parser_rejects_missing_subcommand():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args([])
