# InferBench leaderboard

Auto-rendered from `runs/*.jsonl`. Each row pins the model, subset hash, bench SHA, and InferNode submodule SHA the gate used — historical rows stay comparable even as items/ grows.

## Overall

| Run | Model | Subset | Pass | Rate | Bench | Submodule |
|-----|-------|--------|-----:|-----:|-------|-----------|
| `20260518-172331` | `gptoss-v4-e1` | smoke (`c73efdadd440`) | 6/49 | 12.2% | `e848672103a9` | `c0a33b08c0b8` |
| `20260518-174116` | `gpt-oss:20b` | smoke (`c73efdadd440`) | 0/49 | 0.0% | `e848672103a9` | `` |

## Per-category pass rate

| Run | Model | 9p_tool_use | fs_concepts | inferno_sh | limbo_authoring | plan9_c |
|---|---|---|---|---|---|---|
| `20260518-172331` | `gptoss-v4-e1` | 1/15 | 1/6 | 0/8 | 4/15 | 0/5 |
| `20260518-174116` | `gpt-oss:20b` | 0/15 | 0/6 | 0/8 | 0/15 | 0/5 |

## Per-difficulty pass rate

| Run | Model | trivial | easy | medium | hard |
|---|---|---|---|---|---|
| `20260518-172331` | `gptoss-v4-e1` | 0/6 | 4/24 | 2/18 | 0/1 |
| `20260518-174116` | `gpt-oss:20b` | 0/6 | 0/24 | 0/18 | 0/1 |
