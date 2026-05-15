"""lm-evaluation-harness task pack for InferBench.

Install:
    pip install -e /path/to/infernode-bench
    pip install lm-eval

Run:
    INFERNODE_OS_LLM=/path/to/infernode-os-llm \\
    lm_eval --tasks inferbench_smoke \\
        --model openai-chat-completions \\
        --model_args model=gpt-oss:20b,base_url=http://localhost:11434/v1

Tasks registered:
    inferbench_smoke    50-item smoke subset
    inferbench_mini     ~150-item stratified subset
    inferbench_full     every public item

Each task delegates to `infernode_bench.graders.grade()`, so the same
compile-gate / trace-match / MCQ / judge graders are used as in the
native runner.
"""

from infernode_bench.runners.lm_eval_harness.task import (
    InferBenchTask,
    register_all,
)

__all__ = ["InferBenchTask", "register_all"]
