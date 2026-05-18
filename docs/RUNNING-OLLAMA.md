# Running InferBench against an Ollama-hosted fine-tune

Notes for getting comparable-to-leaderboard results when serving a
gpt-oss fine-tune through Ollama. The default behavior of
`ollama create … FROM ./merged.gguf` will silently score 0% even for
a working merge — three independent gotchas, each fully explanatory.

## TL;DR — Modelfile you need

```
FROM ./your-merged.gguf

PARAMETER temperature 0.0
PARAMETER repeat_penalty 1.3
PARAMETER num_ctx 4096
PARAMETER stop "<|return|>"

TEMPLATE """<full gpt-oss harmony template, copy verbatim from
            `ollama show gpt-oss:20b --verbose`>"""
```

then `ollama show <name> --verbose` and confirm the `template:`
field is the multi-thousand-character harmony template, *not*
`{{ .Prompt }}`.

## Why each parameter matters

### `FROM ./your-merged.gguf` does NOT inherit a chat template
`ollama create` treats raw-GGUF `FROM`s as brand-new models and
defaults to `TEMPLATE {{ .Prompt }}`. For `/v1/chat/completions`,
that means the runtime concatenates `system` + `user` messages as
plain text and hands them to a model trained to expect harmony's
`<|start|>system<|message|>…<|end|><|start|>user<|message|>…` framing.
The model produces gibberish (repetition loops, Python pseudo-code,
internal-reasoning fragments) — *not* because the merge is broken,
because the model never sees the role wrappers it was trained on.

Fix: extract the base's template via
`ollama show gpt-oss:20b --verbose | jq -r '.template'`
and inline the full 7+ KB Go template under `TEMPLATE """ … """`
in your Modelfile.

### `PARAMETER stop "<|end|>"` is **wrong** for gpt-oss
`<|end|>` is the *channel separator* between the model's `analysis`
(internal reasoning) and `final` (user-visible) channels — not the
EOS. Using it as a stop kills generation right after the model
finishes thinking, before it writes the answer. The actual EOS is
`<|return|>`.

Symptom: chat completions return empty strings, `finish_reason: stop`,
~20s elapsed (consistent with one analysis-channel pass).

### `repeat_penalty` defaults too low for these fine-tunes
Out of the box (`repeat_penalty=1.1` or the Ollama default 1.1), the
fine-tune produces the right Limbo preamble (`implement Foo;`,
includes, ADT decl, `Foo: module { … };`) and then loops on the same
declarations until `max_tokens` is hit. Bumping to `1.3` cleanly
breaks the loop. Sweep on `adt_point_v1` showed identical (clean)
output at 1.3, 1.5, 1.8 — no measurable difference once the loop is
broken.

This is a property of the *fine-tune*, not the base. Reproduces
identically on the v3 fine-tune (`gpt-oss-limbo-v3-merged`).

## Result config used for the leaderboard entry

Run `20260518-172331` (`gptoss-v4-e1`, 12.2% smoke) used:
- Template: full gpt-oss harmony template, copied verbatim from
  `ollama show gpt-oss:20b --verbose` at the time of the run.
- Parameters: `temperature=0.0  repeat_penalty=1.3  num_ctx=4096
  stop="<|return|>"`.
- CLI: `python -m infernode_bench run smoke --model gptoss-v4-e1
  --base-url http://127.0.0.1:11434/v1 --temperature 0.0
  --max-tokens 800 --num-ctx 4096 --timeout 240`.
- `INFERNODE_OS_LLM` env var pointed at a checkout of `infernode-os-llm`
  with submodule SHA `c0a33b08c0b8` (the InferNode interface contracts
  the compile gate validates against).

Baseline run `20260518-174116` (`gpt-oss:20b`, 0% smoke) used the same
CLI args against the unmodified `gpt-oss:20b` Modelfile shipped by
Ollama, no Modelfile patches. The 0% reflects that gpt-oss-20b out of
the box routes its output to the suppressed `analysis` channel for 34
of the 49 chat completions, and for the 14 it does answer visibly
(mostly Plan 9 C), none happens to compile-clean.

## Cross-references

See [GPT-OSS-V4-MERGE.md](https://github.com/pdfinn/infernode-os-llm/blob/main/docs/gpt-oss/GPT-OSS-V4-MERGE.md)
in `infernode-os-llm` for the full merge pipeline including the
custom per-expert MoE LoRA bake required for PEFT
`target_parameters` adapters (a different problem from this doc —
that's about producing a *correct* merged GGUF; this is about getting
*correct results* out of it).
