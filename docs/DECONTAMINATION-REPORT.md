# Decontamination report

- k-gram size: 13
- prompt-overlap threshold (flag if ≥): 3
- golden-overlap threshold (informational): 30
- items audited: 260
- items flagged (on prompt overlap): 3

Policy: Flag on prompt overlap only. Goldens share idiomatic boilerplate (include statements, init signatures) with the InferNode tree by construction — that's not contamination.

## Corpora

| Corpus | Path | Status | k-grams |
|--------|------|--------|--------:|
| infernode | `/home/user/infernode-os-llm/infernode` | ok | 6096717 |
| plan9port | `/tmp/plan9port` | ok | 4206138 |
| upstream_inferno_os | `—` | skipped (path missing) | — |
| ipm | `—` | skipped (path missing) | — |

## Flagged items

| Item | Category | Flagged against | Top prompt overlap |
|------|----------|------------------|-------------------:|
| `line_count_v1` | limbo_authoring | infernode | infernode=4 |
| `limbo_raise_simple_v1` | limbo_authoring | infernode | infernode=3 |
| `c_sysfatal_v1` | plan9_c | plan9port | plan9port=4 |
