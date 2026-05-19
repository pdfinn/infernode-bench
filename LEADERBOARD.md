# InferBench leaderboard

Auto-rendered from `runs/*.jsonl`. Each row pins the model, subset hash, bench SHA, and InferNode submodule SHA the gate used — historical rows stay comparable even as items/ grows.

## Overall

| Run | Model | Subset | Pass | Rate | Trunc | Bench | Submodule |
|-----|-------|--------|-----:|-----:|------:|-------|-----------|
| `20260518-232427` | `gptoss-v4-e1` | smoke (`c73efdadd440`) | 18/49 | 36.7% | 2 | `7f10275d41ae` | `c0a33b08c0b8` |
| `20260518-233753` | `gpt-oss:20b` | smoke (`c73efdadd440`) | 7/49 | 14.3% | 2 | `28ff36d45663` | `` |
| `20260519-003851` | `gptoss-v4-e1` | mini (`02a3a7e02846`) | 45/150 | 30.0% | 26 | `ddb55fe7157f` | `c0a33b08c0b8` |
| `20260519-011319` | `gpt-oss:20b` | mini (`02a3a7e02846`) | 49/150 | 32.7% | 28 | `ddb55fe7157f` | `` |

## Per-category pass rate

| Run | Model | 9p_tool_use | fs_concepts | inferno_sh | limbo_authoring | plan9_c |
|---|---|---|---|---|---|---|
| `20260518-232427` | `gptoss-v4-e1` | 7/15 | 3/6 | 4/8 | 4/15 | 0/5 |
| `20260518-233753` | `gpt-oss:20b` | 0/15 | 0/6 | 3/8 | 0/15 | 4/5 |
| `20260519-003851` | `gptoss-v4-e1` | 6/39 | 18/26 | 6/26 | 14/40 | 1/19 |
| `20260519-011319` | `gpt-oss:20b` | 1/39 | 21/26 | 11/26 | 0/40 | 16/19 |

## Per-difficulty pass rate

| Run | Model | trivial | easy | medium | hard |
|---|---|---|---|---|---|
| `20260518-232427` | `gptoss-v4-e1` | 2/6 | 12/24 | 4/18 | 0/1 |
| `20260518-233753` | `gpt-oss:20b` | 1/6 | 5/24 | 1/18 | 0/1 |
| `20260519-003851` | `gptoss-v4-e1` | 6/10 | 14/59 | 16/61 | 9/20 |
| `20260519-011319` | `gpt-oss:20b` | 4/10 | 20/59 | 20/61 | 5/20 |

## Per-context-freshness pass rate

| Run | Model | cold | primed | concept |
|---|---|---|---|---|
| `20260518-232427` | `gptoss-v4-e1` | 18/49 | — | — |
| `20260518-233753` | `gpt-oss:20b` | 7/49 | — | — |
| `20260519-003851` | `gptoss-v4-e1` | 45/150 | — | — |
| `20260519-011319` | `gpt-oss:20b` | 49/150 | — | — |
