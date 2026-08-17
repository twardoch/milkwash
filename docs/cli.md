---
this_file: docs/cli.md
title: Command line
layout: default
nav_order: 4
permalink: /cli/
---

# The milkwashy command

`milkwashy` uses [Fire](https://github.com/google/python-fire). Each command
accepts `-- --help`, which shows all of its flags:

```bash
milkwashy run -- --help
```

Two flags work for all commands:

| Flag | Default | Function |
|:-----|:--------|:---------|
| `--project_dir` | `.` | The directory that holds `01-indata/` and `02-testllm/`. |
| `--verbose` | `True` | Shows the log messages. Give `--verbose=False` to hide them. |

## Configuration commands

```bash
milkwashy init_config          # write the default TOML configuration
milkwashy init_config --force   # replace an existing file
milkwashy config_path           # print the location of the file
```

## Input commands

```bash
milkwashy gen_indata            # write the four example texts to 01-indata/
```

The texts are in English, Polish, German and Arabic. They come from the package,
so the command needs no network. The file names hold the language code, for
example `en__en-rivers-and-machines.txt`.

## Model commands

```bash
milkwashy models                        # list the models of the default server
milkwashy models --provider cliproxy    # list the models of one other server
milkwashy lms_status                    # show the LM Studio state
milkwashy lms_unload_all                # unload all models, and confirm it
```

The list is in order of size, from the smallest model to the largest. `--limit N`
in the `run` command then always selects the same models.

## Plan command

```bash
milkwashy plan
```

This command shows the chunks and the prompt for each input text. It sends
nothing to a model, so it is fast and it costs nothing. Use it to see the plan
before a long sweep.

## Sweep command

```bash
milkwashy run                        # all models of the default server
milkwashy run --limit 5              # the 5 smallest models
milkwashy run --max_size_mb 8000     # skip models above 8 GB
milkwashy run --provider chat2api    # one other server
milkwashy run --manage_lms=False     # do not load or unload models
milkwashy run --force                # write the output files again
```

| Flag | Default | Function |
|:-----|:--------|:---------|
| `--provider` | the default in the configuration | Which server to use. |
| `--limit` | no limit | Use only the N smallest models. |
| `--max_size_mb` | no limit | Skip each model that is larger than this size. |
| `--manage_lms` | `True` | Let milkwashy load and unload LM Studio models. |
| `--force` | `False` | Make the requests again, and replace the output files. |

The sweep writes to
`02-testllm/<server>/<model>/<text>.txt`, and it writes the plan next to each
output as `<text>.plan.json`.

{: .note }
> A sweep can continue. If an output file is present, milkwashy does not make the
> request again. If all of the output files of a model are present, milkwashy does
> not load that model. Give `--force` to ignore this rule.

## All servers together

The `sweep.sh` script in the repository starts one process for each server. The
processes run at the same time.

```bash
./sweep.sh                        # all servers
./sweep.sh --limit 5              # the 5 smallest models of each server
PROVIDERS="lmstudio" ./sweep.sh   # one server only
PARALLEL=0 ./sweep.sh             # one server after the other
```

Each process writes its own log file to `02-testllm/_logs/<server>.log`. Use
`tail -f` to watch a log.

Only one LM Studio sweep can run on a computer. The script uses a lock
directory, because two sweeps would load and unload models at the same time. A
second LM Studio sweep stops with a message. The other servers in that command
continue.

## From Python

```python
from pathlib import Path

import milkwashy

text = "Rivers move. Machines stop. Nobody remembers the first winter."

seed = milkwashy.text_seed(text)
for plan in milkwashy.plan_chunks(text, "en"):
    print(plan.index, plan.prompt_index, plan.text)

config = milkwashy.load_config()
provider = config.providers[config.default_provider]
result = milkwashy.run_sweep(
    config,
    provider,
    project_dir=Path("."),
    limit=1,
)
print(result)
```

## From Rust

```rust
use milkwashr::{assemble_chunks, text_seed};

let sentences: Vec<String> = vec!["Rivers move.".into(), "Machines stop.".into()];
let seed = text_seed(&sentences.join(" "));
let chunks = assemble_chunks(&sentences, seed, 2, 8, 6000);
```
