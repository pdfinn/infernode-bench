"""Task subclass that exposes InferBench subsets to lm-evaluation-harness.

The task contract:
- `download` is a no-op (items live in the bench repo).
- `training_docs` / `validation_docs` are empty — no train/dev split.
- `test_docs` returns the resolved subset.
- `doc_to_text` produces the prompt sent to the model.
- `doc_to_target` is the empty string (we don't grade on textual
  similarity — the bench's own graders run on the model's completion).
- `process_results` calls `infernode_bench.graders.grade()` and returns
  the `ok` value as the per-item metric.

The harness's `generate_until` request type is used: free-form
generation, no logprobs. Stop sequences are unused; the bench's grader
extracts code from the model's full response.
"""

from __future__ import annotations

from typing import Any

try:
    from lm_eval.api.task import ConfigurableTask, TaskConfig
    from lm_eval.api.instance import Instance
    from lm_eval.api.registry import register_task
    HAVE_LM_EVAL = True
except ImportError:  # lm-eval not installed
    HAVE_LM_EVAL = False
    ConfigurableTask = object   # type: ignore[assignment,misc]
    TaskConfig = None           # type: ignore[assignment]
    Instance = None             # type: ignore[assignment]
    def register_task(name):    # type: ignore[no-redef]
        def deco(cls):
            return cls
        return deco

from infernode_bench.graders import grade
from infernode_bench.subset import load_subset, resolve_subset


DEFAULT_SYSTEM_PROMPT = (
    "You are an expert programmer for the Inferno operating system "
    "(Limbo, Plan 9 idiom C, Inferno sh, 9P-native tool use). When asked "
    "for code, respond with one complete, compilable source file inside a "
    "single fenced code block tagged for the appropriate language. Do not "
    "add explanation outside the code fence."
)


class InferBenchTask(ConfigurableTask):
    """Base class. Subclasses set `SUBSET_NAME`."""

    VERSION = 0
    SUBSET_NAME: str = ""

    def __init__(self, *args, **kwargs):
        if not HAVE_LM_EVAL:
            raise RuntimeError(
                "lm-eval-harness is not installed; "
                "`pip install lm-eval` to use this task."
            )
        # ConfigurableTask normally loads from YAML; we provide config
        # inline so external users don't need to ship task YAMLs.
        config = TaskConfig(
            task=f"inferbench_{self.SUBSET_NAME}",
            output_type="generate_until",
            test_split="test",
            doc_to_text=self.doc_to_text,
            doc_to_target=self.doc_to_target,
            metric_list=[{"metric": "pass", "aggregation": "mean",
                          "higher_is_better": True}],
            generation_kwargs={
                "max_gen_toks": 2048,
                "temperature": 0.0,
                "do_sample": False,
                "until": [],
            },
        )
        super().__init__(config=config)
        self._items = resolve_subset(load_subset(self.SUBSET_NAME))

    # The task surface --------------------------------------------------

    def has_training_docs(self):
        return False

    def has_validation_docs(self):
        return False

    def has_test_docs(self):
        return True

    def test_docs(self):
        return iter(self._items)

    def doc_to_text(self, doc):   # type: ignore[override]
        return f"{DEFAULT_SYSTEM_PROMPT}\n\n{doc['prompt']}"

    def doc_to_target(self, doc):   # type: ignore[override]
        return ""

    def construct_requests(self, doc, ctx, **kwargs):   # type: ignore[override]
        return [Instance(
            request_type="generate_until",
            doc=doc,
            arguments=(ctx, {"max_gen_toks": 2048, "until": []}),
            idx=0,
            **kwargs,
        )]

    def process_results(self, doc, results) -> dict[str, Any]:   # type: ignore[override]
        completion = results[0] if results else ""
        try:
            gr = grade(doc, completion)
            ok = 1 if gr.ok else 0
        except Exception:
            ok = 0
        return {"pass": ok}

    def aggregation(self):   # type: ignore[override]
        return {"pass": _mean}

    def higher_is_better(self):   # type: ignore[override]
        return {"pass": True}


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


@register_task("inferbench_smoke")
class InferBenchSmoke(InferBenchTask):
    SUBSET_NAME = "smoke"


@register_task("inferbench_mini")
class InferBenchMini(InferBenchTask):
    SUBSET_NAME = "mini"


@register_task("inferbench_full")
class InferBenchFull(InferBenchTask):
    SUBSET_NAME = "full"


def register_all() -> list[str]:
    """Idempotent registration helper; returns the task names registered.

    Useful as `lm_eval --include_path /path/to/this/dir` if the user
    wants to point lm-eval at the package without installing it."""
    return ["inferbench_smoke", "inferbench_mini", "inferbench_full"]
