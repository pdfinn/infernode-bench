# InferBench — Makefile
#
# Conventions match infernode-os-llm: targets are the contract for
# "what can I run?". `make help` lists everything.

PY ?= python3
PIP ?= $(PY) -m pip

.PHONY: help install lint test validate subset-hashes smoke mini full clean

help:  ## list targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install:  ## install the package in editable mode + dev extras
	$(PIP) install -e .[dev]

lint:  ## ruff lint the python package
	$(PY) -m ruff check infernode_bench tests

test:  ## run the pytest suite
	$(PY) -m pytest tests/ -v

validate:  ## schema-validate every item; non-zero exit on any failure
	$(PY) -m infernode_bench validate

subset-hashes:  ## print the resolved hash for every subset
	$(PY) -m infernode_bench subset hashes

# ---------- run a subset ----------------------------------------------------
# Override MODEL, BASE_URL, INFERNODE_OS_LLM as needed.
MODEL ?= gpt-oss:20b
BASE_URL ?= http://localhost:11434/v1

smoke:  ## run the smoke subset (MODEL=$(MODEL) BASE_URL=$(BASE_URL))
	$(PY) -m infernode_bench run smoke --model $(MODEL) --base-url $(BASE_URL)

mini:  ## run the mini subset
	$(PY) -m infernode_bench run mini --model $(MODEL) --base-url $(BASE_URL)

full:  ## run the full subset
	$(PY) -m infernode_bench run full --model $(MODEL) --base-url $(BASE_URL)

clean:  ## remove build + pytest + ruff caches
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
