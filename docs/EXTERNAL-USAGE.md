# External usage

InferBench can be run two ways: via its own CLI, or as a task pack for
Eleuther's `lm-evaluation-harness`.

## Native CLI

```sh
pip install -e .
export INFERNODE_OS_LLM=/path/to/infernode-os-llm    # for the compile gate
python -m infernode_bench run smoke \
    --model gpt-oss:20b \
    --base-url http://localhost:11434/v1
```

Emits per-item JSONL to `runs/<run_id>_smoke_<model>.jsonl` and a
summary to stderr. The summary includes:

```json
{
  "subset_hash": "b8d81aea0ae68dd1…",
  "bench_sha": "ddb09f4…",
  "model": "gpt-oss:20b",
  "n_items": 49,
  "n_pass": 42,
  "pass_rate": 0.857
}
```

## lm-evaluation-harness

```sh
pip install -e .
pip install lm-eval
export INFERNODE_OS_LLM=/path/to/infernode-os-llm

lm_eval --tasks inferbench_smoke \
    --model openai-chat-completions \
    --model_args model=gpt-oss:20b,base_url=http://localhost:11434/v1
```

Tasks: `inferbench_smoke`, `inferbench_mini`, `inferbench_full`. Each
delegates to `infernode_bench.graders.grade()`, so the bench's own
graders (compile-gate, trace-match, MCQ, judge) run inside the
harness. Per-task metric: `pass` (0/1 per item, mean across items).

### What lm-eval sees

The harness sees a free-form generation task: input is the system +
user prompt, target is the empty string (the harness's similarity
metrics don't apply — the bench grades by the compile gate or trace
match, not by comparing the model output to a reference string).

### Why two surfaces

The native CLI is faster, knows about IOL's compile gate by default,
and produces JSONL whose schema (`schema/result.schema.json`) the
leaderboard renderer consumes directly. The lm-eval task pack is
slower but plugs into the third-party harness ecosystem so InferBench
can appear alongside MMLU/GSM8K/HumanEval in side-by-side eval reports.
