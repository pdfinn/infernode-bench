# Run: `devstral:latest` on `mini` — `20260519-105425`

> **Official benchmark record.** This file is the citable record of one
> InferBench run. It is immutable once committed — if methodology
> changes, a new run replaces it.

## Identity

| Field | Value |
|---|---|
| Run ID | `20260519-105425` |
| Model | `devstral:latest` |
| Endpoint | `http://127.0.0.1:11434/v1` |
| Subset | `mini` (hash `02a3a7e02846`) |
| Items | 150 graded (of 150 resolved) |
| Bench SHA | `ac6275650211400f034e7010ae96cf662d1d945b` (`pdfinn/infernode-bench@ac6275650211`) |
| InferNode submodule SHA | `c0a33b08c0b8b1667979516d0f22ca558ba4d4c5` (`pdfinn/infernode-os-llm/infernode@c0a33b08c0b8`) |
| Run timestamp | 2026-05-19T03:55:05.174288Z |

## Configuration

- `max_tokens`: 800, 1500 (per-language per IOL-32)
- `truncated`: 1/150 responses hit the token cap mid-construct
- Endpoint protocol: OpenAI-compatible `/v1/chat/completions`
- `temperature`: 0.0 (deterministic)

## Headline result

**40/150 pass — 26.7%** — 1 truncated

### Per category

| Category | Pass | Total | Rate |
|---|---:|---:|---:|
| 9p_tool_use | 1 | 39 | 2.6% |
| fs_concepts | 7 | 26 | 26.9% |
| inferno_sh | 17 | 26 | 65.4% |
| limbo_authoring | 0 | 40 | 0.0% |
| plan9_c | 15 | 19 | 78.9% |

### Per difficulty

| Difficulty | Pass | Total | Rate |
|---|---:|---:|---:|
| easy | 20 | 59 | 33.9% |
| hard | 3 | 20 | 15.0% |
| medium | 12 | 61 | 19.7% |
| trivial | 5 | 10 | 50.0% |

### Per context freshness

| Freshness | Pass | Total | Rate |
|---|---:|---:|---:|
| cold | 40 | 150 | 26.7% |

## Items

| Item | Category | Difficulty | Result | Elapsed |
|---|---|---|---|---:|
| `tool_chain_find_then_read_each_v1` | 9p_tool_use | medium | FAIL | 4.3s |
| `tool_chain_git_then_diff_v1` | 9p_tool_use | hard | FAIL | 21.2s |
| `tool_charon_browse_v1` | 9p_tool_use | easy | FAIL | 3.1s |
| `tool_concurrent_grep_v1` | 9p_tool_use | medium | FAIL | 36.7s |
| `tool_ctl_then_data_v1` | 9p_tool_use | medium | FAIL | 4.8s |
| `tool_data_streaming_v1` | 9p_tool_use | hard | FAIL | 24.3s |
| `tool_doc_for_missing_v1` | 9p_tool_use | easy | FAIL | 12.7s |
| `tool_doc_then_doc_v1` | 9p_tool_use | easy | FAIL | 20.5s |
| `tool_doc_then_invoke_v1` | 9p_tool_use | medium | FAIL | 9.0s |
| `tool_fractal_render_v1` | 9p_tool_use | medium | FAIL | 10.1s |
| `tool_gpu_v1` | 9p_tool_use | hard | FAIL | 11.8s |
| `tool_help_for_tool_v1` | 9p_tool_use | medium | FAIL | 35.2s |
| `tool_invoke_grep_rc_v1` | 9p_tool_use | trivial | FAIL | 3.9s |
| `tool_invoke_with_argv_v1` | 9p_tool_use | easy | FAIL | 38.7s |
| `tool_limbo_argv_dispatch_v1` | 9p_tool_use | hard | FAIL | 30.5s |
| `tool_limbo_driven_writefile_v1` | 9p_tool_use | medium | FAIL | 20.1s |
| `tool_limbo_paths_v1` | 9p_tool_use | medium | FAIL | 27.0s |
| `tool_memory_get_v1` | 9p_tool_use | easy | FAIL | 12.5s |
| `tool_payfetch_v1` | 9p_tool_use | medium | FAIL | 26.4s |
| `tool_rc_for_each_tool_v1` | 9p_tool_use | hard | FAIL | 4.8s |
| `tool_rc_vs_limbo_same_intent_v1` | 9p_tool_use | medium | FAIL | 3.7s |
| `tool_read_doc_v1` | 9p_tool_use | trivial | PASS | 2.1s |
| `tool_register_check_then_invoke_v1` | 9p_tool_use | medium | FAIL | 32.5s |
| `tool_run_diff_v1` | 9p_tool_use | easy | FAIL | 4.2s |
| `tool_run_json_v1` | 9p_tool_use | easy | FAIL | 3.8s |
| `tool_run_list_dir_v1` | 9p_tool_use | easy | FAIL | 17.5s |
| `tool_run_mail_v1` | 9p_tool_use | medium | FAIL | 9.8s |
| `tool_run_man_then_say_v1` | 9p_tool_use | medium | FAIL | 7.0s |
| `tool_run_websearch_v1` | 9p_tool_use | easy | FAIL | 3.0s |
| `tool_safeexec_run_v1` | 9p_tool_use | easy | FAIL | 5.7s |
| `tool_spawn_run_v1` | 9p_tool_use | easy | FAIL | 7.2s |
| `tool_status_check_v1` | 9p_tool_use | medium | FAIL | 22.9s |
| `tool_stream_exec_v1` | 9p_tool_use | medium | FAIL | 27.0s |
| `tool_stream_hear_v1` | 9p_tool_use | hard | FAIL | 22.9s |
| `tool_translate_json_limbo_v1` | 9p_tool_use | medium | FAIL | 13.4s |
| `tool_use_man_v1` | 9p_tool_use | easy | FAIL | 25.8s |
| `tool_use_shell_v1` | 9p_tool_use | easy | FAIL | 18.4s |
| `tool_walk_root_v1` | 9p_tool_use | trivial | FAIL | 1.7s |
| `tool_webfetch_with_headers_v1` | 9p_tool_use | medium | FAIL | 22.5s |
| `fs_afid_nofid_v1` | fs_concepts | hard | FAIL | 4.0s |
| `fs_apid_vs_pid_v1` | fs_concepts | medium | PASS | 10.2s |
| `fs_chgrp_via_wstat_v1` | fs_concepts | medium | FAIL | 8.1s |
| `fs_clone_walk_v1` | fs_concepts | medium | FAIL | 2.7s |
| `fs_create_perm_v1` | fs_concepts | easy | PASS | 7.2s |
| `fs_ctl_send_command_v1` | fs_concepts | easy | FAIL | 14.1s |
| `fs_dev_consensus_v1` | fs_concepts | easy | FAIL | 2.1s |
| `fs_dial_purpose_v1` | fs_concepts | easy | FAIL | 9.3s |
| `fs_dirread_offset_v1` | fs_concepts | hard | FAIL | 17.6s |
| `fs_dirread_open_required_v1` | fs_concepts | easy | FAIL | 23.4s |
| `fs_dirread_partial_v1` | fs_concepts | hard | FAIL | 20.4s |
| `fs_export_dial_v1` | fs_concepts | hard | PASS | 2.4s |
| `fs_factotum_v1` | fs_concepts | medium | FAIL | 16.0s |
| `fs_mountfd_v1` | fs_concepts | medium | FAIL | 12.5s |
| `fs_namespace_export_v1` | fs_concepts | medium | PASS | 4.5s |
| `fs_oexcl_v1` | fs_concepts | medium | FAIL | 9.7s |
| `fs_oexec_v1` | fs_concepts | medium | FAIL | 12.6s |
| `fs_oread_meaning_v1` | fs_concepts | trivial | PASS | 13.2s |
| `fs_proc_status_layout_v1` | fs_concepts | medium | FAIL | 22.0s |
| `fs_qid_type_v1` | fs_concepts | medium | FAIL | 9.4s |
| `fs_qid_uniqueness_v1` | fs_concepts | medium | PASS | 10.7s |
| `fs_read_status_lines_v1` | fs_concepts | medium | FAIL | 14.8s |
| `fs_rename_via_wstat_v1` | fs_concepts | medium | FAIL | 15.6s |
| `fs_tag_uniqueness_v1` | fs_concepts | medium | FAIL | 13.3s |
| `fs_unmount_v1` | fs_concepts | easy | FAIL | 2.2s |
| `fs_walk_count_limit_v1` | fs_concepts | hard | PASS | 13.6s |
| `rc_alt_run_v1` | inferno_sh | easy | PASS | 2.5s |
| `rc_for_loop_v1` | inferno_sh | trivial | FAIL | 2.7s |
| `rc_function_v1` | inferno_sh | easy | FAIL | 6.1s |
| `rc_redirect_v1` | inferno_sh | easy | PASS | 2.8s |
| `rc_tool_chain_v1` | inferno_sh | medium | FAIL | 6.1s |
| `sh_apid_in_path_v1` | inferno_sh | easy | PASS | 3.3s |
| `sh_check_status_v1` | inferno_sh | medium | FAIL | 3.4s |
| `sh_combine_redirects_v1` | inferno_sh | medium | PASS | 2.8s |
| `sh_command_substitution_v1` | inferno_sh | easy | PASS | 2.8s |
| `sh_count_files_v1` | inferno_sh | medium | FAIL | 4.1s |
| `sh_export_var_v1` | inferno_sh | easy | PASS | 2.0s |
| `sh_fn_with_args_v1` | inferno_sh | easy | PASS | 3.3s |
| `sh_if_else_v1` | inferno_sh | easy | FAIL | 4.0s |
| `sh_list_quoting_v1` | inferno_sh | easy | FAIL | 3.5s |
| `sh_load_module_v1` | inferno_sh | easy | PASS | 2.3s |
| `sh_no_for_paren_v1` | inferno_sh | easy | FAIL | 2.6s |
| `sh_no_if_paren_v1` | inferno_sh | easy | FAIL | 2.5s |
| `sh_or_fallback_v1` | inferno_sh | easy | PASS | 3.6s |
| `sh_pipe_three_v1` | inferno_sh | medium | PASS | 2.3s |
| `sh_pwd_cd_v1` | inferno_sh | trivial | PASS | 2.2s |
| `sh_redirect_in_out_v1` | inferno_sh | easy | PASS | 2.3s |
| `sh_run_or_default_v1` | inferno_sh | medium | PASS | 3.9s |
| `sh_subshell_capture_v1` | inferno_sh | medium | PASS | 2.6s |
| `sh_var_assign_print_v1` | inferno_sh | trivial | PASS | 2.6s |
| `sh_var_default_v1` | inferno_sh | easy | PASS | 2.6s |
| `sh_veltro_invoke_v1` | inferno_sh | easy | PASS | 2.9s |
| `alt_demux_v1` | limbo_authoring | medium | FAIL | 39.9s |
| `chan_pipeline_v1` | limbo_authoring | hard | FAIL | 25.1s |
| `error_handling_open_v1` | limbo_authoring | easy | FAIL | 18.3s |
| `hello_world_v1` | limbo_authoring | trivial | FAIL ⊘ | 5.5s |
| `limbo_alt_timeout_v1` | limbo_authoring | medium | FAIL | 10.1s |
| `limbo_array_slice_v1` | limbo_authoring | medium | FAIL | 13.6s |
| `limbo_big_arithmetic_v1` | limbo_authoring | easy | FAIL | 13.1s |
| `limbo_break_continue_v1` | limbo_authoring | easy | FAIL | 8.9s |
| `limbo_bufio_putc_v1` | limbo_authoring | easy | FAIL | 26.0s |
| `limbo_bugfix_array_len_v1` | limbo_authoring | easy | FAIL | 11.7s |
| `limbo_bugfix_module_load_v1` | limbo_authoring | easy | FAIL | 11.3s |
| `limbo_byte_array_string_v1` | limbo_authoring | medium | FAIL | 19.3s |
| `limbo_chan_buffered_v1` | limbo_authoring | easy | FAIL | 12.2s |
| `limbo_chan_of_chan_v1` | limbo_authoring | hard | FAIL | 13.1s |
| `limbo_chan_status_struct_v1` | limbo_authoring | hard | FAIL | 15.9s |
| `limbo_concurrent_collect_v1` | limbo_authoring | hard | FAIL | 17.9s |
| `limbo_draw_load_v1` | limbo_authoring | easy | FAIL | 6.5s |
| `limbo_errstr_propagate_v1` | limbo_authoring | medium | FAIL | 14.0s |
| `limbo_fan_out_v1` | limbo_authoring | medium | FAIL | 17.2s |
| `limbo_fprint_stderr_v1` | limbo_authoring | trivial | FAIL | 7.8s |
| `limbo_iter_dirread_v1` | limbo_authoring | hard | FAIL | 10.4s |
| `limbo_keyring_load_v1` | limbo_authoring | easy | FAIL | 8.9s |
| `limbo_list_filter_v1` | limbo_authoring | medium | FAIL | 17.8s |
| `limbo_mod_func_v1` | limbo_authoring | easy | FAIL | 17.6s |
| `limbo_multiple_exceptions_v1` | limbo_authoring | hard | FAIL | 11.4s |
| `limbo_no_auto_struct_v1` | limbo_authoring | medium | FAIL | 11.9s |
| `limbo_pick_default_v1` | limbo_authoring | medium | FAIL | 20.8s |
| `limbo_pick_with_methods_v1` | limbo_authoring | hard | FAIL | 14.2s |
| `limbo_raise_simple_v1` | limbo_authoring | easy | FAIL | 7.0s |
| `limbo_security_random_v1` | limbo_authoring | easy | FAIL | 12.5s |
| `limbo_self_check_loaded_v1` | limbo_authoring | medium | FAIL | 12.7s |
| `limbo_string_drop_take_v1` | limbo_authoring | medium | FAIL | 16.1s |
| `limbo_string_in_v1` | limbo_authoring | medium | FAIL | 12.2s |
| `limbo_string_tolower_v1` | limbo_authoring | easy | FAIL | 9.7s |
| `limbo_strings_are_bytes_v1` | limbo_authoring | medium | FAIL | 6.3s |
| `limbo_sys_bind_v1` | limbo_authoring | medium | FAIL | 12.3s |
| `limbo_sys_sprint_format_v1` | limbo_authoring | easy | FAIL | 11.8s |
| `limbo_sys_stat_size_v1` | limbo_authoring | medium | FAIL | 20.4s |
| `limbo_tuple_unpack_v1` | limbo_authoring | easy | FAIL | 11.6s |
| `line_count_v1` | limbo_authoring | easy | FAIL | 17.2s |
| `c_args_parse_v1` | plan9_c | medium | PASS | 12.9s |
| `c_atoi_v1` | plan9_c | easy | PASS | 8.2s |
| `c_bigbuf_loop_v1` | plan9_c | medium | PASS | 9.0s |
| `c_bio_brdline_v1` | plan9_c | medium | FAIL | 15.5s |
| `c_bio_write_v1` | plan9_c | medium | FAIL | 7.4s |
| `c_chdir_v1` | plan9_c | easy | PASS | 6.5s |
| `c_dial_v1` | plan9_c | medium | PASS | 10.3s |
| `c_dirread_loop_v1` | plan9_c | medium | PASS | 16.6s |
| `c_errstr_pattern_v1` | plan9_c | easy | PASS | 11.7s |
| `c_fmtprint_buffer_v1` | plan9_c | medium | FAIL | 7.1s |
| `c_getenv_v1` | plan9_c | easy | PASS | 7.1s |
| `c_getuser_v1` | plan9_c | easy | PASS | 5.1s |
| `c_no_stdio_v1` | plan9_c | medium | PASS | 4.0s |
| `c_rfork_v1` | plan9_c | hard | PASS | 8.4s |
| `c_sleep_v1` | plan9_c | trivial | PASS | 4.5s |
| `c_sysfatal_v1` | plan9_c | easy | PASS | 11.5s |
| `c_thread_chan_v1` | plan9_c | hard | FAIL | 19.0s |
| `c_thread_main_basic_v1` | plan9_c | easy | PASS | 5.9s |
| `c_werrstr_v1` | plan9_c | easy | PASS | 11.2s |

## Notable failures

### `alt_demux_v1` (limbo_authoring, medium)

**Gate stderr (tail):**
```
/tmp/limbogate-6acyligj/src.b:7: near ` { ` : syntax error
/tmp/limbogate-6acyligj/src.b:11: near ` spawn ` : syntax error
```
**Response (first 400 chars):**
```
```limbo
include "sys.m";
include "draw.m";

init: fn(nil: ref Draw->Display, nil: list of string)
{
	a := chan of string;
	b := chan of string;

	spawn {
		send a "from a";
	};

	spawn {
		send b "from b";
	};

	alt
	{
	case msg := <-a:
		sys->print("Received: %s\n", msg);
	case msg := <-b:
		sys->print("Received: %s\n", msg);
	}

	exit;
}
```
```

### `c_bio_brdline_v1` (plan9_c, medium)

**Gate stderr (tail):**
```
getline’ [-Wimplicit-function-declaration]
   18 |         while(Bgetline(b, buf, sizeof(buf)) != nil){
      |               ^~~~~~~~
/tmp/p9cgate-senqw6ov/src.c:18:45: warning: comparison between pointer and integer
   18 |         while(Bgetline(b, buf, sizeof(buf)) != nil){
      |                                             ^~
/tmp/p9cgate-senqw6ov/src.c:22:9: warning: implicit declaration of function ‘Bterm’ [-Wimplicit-function-declaration]
   22 |         Bterm(b);
      |         ^~~~~
```
**Response (first 400 chars):**
```
```c
#include <u.h>
#include <libc.h>

void
main(void)
{
	Biobuf *b;
	char buf[128];
	int n;

	b = Bfdopen(0, OREAD);
	if(b == nil){
		fprint(2, "Bfdopen: %r\n");
		exits("Bfdopen");
	}

	n = 0;
	while(Bgetline(b, buf, sizeof(buf)) != nil){
		n++;
		fprint(1, "%d: %s", n, buf);
	}
	Bterm(b);
	exits(nil);
}
```
```

### `fs_afid_nofid_v1` (fs_concepts, hard)

**Response (first 400 chars):**
```
```limbo
include "sys.m";
include "draw.m";

Tattach(NOFID, 0xFFFFFFFF);
```
```

### `rc_for_loop_v1` (inferno_sh, trivial)

**Gate stderr (tail):**
```
usage: for var in [item...] {cmd}
```
**Response (first 400 chars):**
```
```sh
for (i in red green blue)
    echo colour: $i
```
```

### `tool_chain_find_then_read_each_v1` (9p_tool_use, medium)

**Extracted trace:** `[]`
**Response (first 400 chars):**
```
```sh
#!/bin/rc

find /module -name '*.m' | while read f
read $f | sed q
done
```
```

## Reproduction

```sh
INFERNODE_OS_LLM=/path/to/infernode-os-llm  \
    python -m infernode_bench run  \
    mini  \
    --model "devstral:latest"  \
    --base-url http://127.0.0.1:11434/v1  \
    --temperature 0.0  \
    --num-ctx 4096  \
    --timeout 300
```

JSONL artefact (not in git per `.gitignore`):
`runs/20260519-105425_mini_devstral_latest.jsonl`
