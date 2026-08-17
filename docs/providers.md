---
this_file: docs/providers.md
title: Model servers
layout: default
nav_order: 5
permalink: /providers/
---

# Model servers

All of the requests use the OpenAI chat interface. Any server with that interface
can do the work. milkwashy knows three servers, and you can add more in the
configuration file.

| Name | Default address | Model list from | Notes |
|:-----|:----------------|:----------------|:------|
| `lmstudio` | `http://127.0.0.1:1234/v1` | the `lms` command | The default. It is the only source that reports the size of each model. |
| `chat2api` | `http://127.0.0.1:8318/v1` | `GET /v1/models` | A remote service behind a local port. |
| `cliproxy` | `http://0.0.0.0:18317/v1` | `GET /v1/models` | If the port is closed, milkwashy tries the port minus 10000. |

## Where the settings come from

The order is:

1. The TOML configuration file.
2. The environment. milkwashy reads a `.env` file with `python-dotenv`.
3. The value in the program.

Copy `.env.example` to `.env`, and then write your addresses and keys:

```bash
LMSTUDIO_API_ENDPOINT=http://127.0.0.1:1234/v1
LMSTUDIO_API_KEY=sk-lm-REPLACE_ME

CHAT2API_API_ENDPOINT=http://127.0.0.1:8318/v1
CHAT2API_API_KEY=sk-REPLACE_ME

CLIPROXY_API_ENDPOINT=http://0.0.0.0:18317/v1
CLIPROXY_API_KEY=quotio-local-REPLACE_ME
```

LM Studio does not look at the key. Any value is satisfactory.

## Why the model list is a special case

Each server reports its models in a different form. Only the `lms` command gives
the size of each model in bytes.

milkwashy puts the list in order of `(size, name)`. The size comes first, and the
name breaks a tie. Because of this, `--limit N` always selects the same models,
also for a server that reports no size and no fixed order.

## Why one model only is in memory

A large model can fill the memory of the computer. Two large models cannot both
stay in memory. milkwashy therefore holds one model in memory at a time.

Before each load, `lmsctl.load_exclusive` does these steps:

1. It reads `lms ps --json` to see which models are in memory.
2. It unloads each model that it finds.
3. If a model is still in memory, it runs `lms unload --all`.
4. If the memory is still not empty, it stops the sweep.

The code that runs the model is inside `try` and `finally`. The model therefore
leaves the memory after success, after an error, after a skip, and after you stop
the program with Control-C.

The check is at the load, not at the end of the loop. Every `continue`, every
`break` and every error would be a way to load a second model, if the check were
at the end.

## Why milkwashy makes a test request

The model list of LM Studio also holds models that cannot answer a chat request.
Examples are embedding models, models that read text from images, and models that
make speech.

milkwashy does not try to find these models by their name. It sends one short
request of 8 tokens to each model. If the request fails, milkwashy writes
`_skipped.json` and continues with the next model.

## How a stopped sweep continues

| Situation | Behaviour | Reason |
|:----------|:----------|:-------|
| The output file is present | Skip. Make no request. | The work is complete. |
| All output files of a model are present | Do not load the model. | A load is expensive. |
| The model is marked `load_failed` | Do not try again. | Bad tensors and unknown model types do not repair themselves. |
| The model is marked `probe_failed` | Try again. | One wrong port marks all of the models. A permanent mark would then make a corrected sweep do nothing. |
| You give `--force` | Make all of the requests again. | You asked for new output. |

To continue a sweep that stopped, give the same command again.

## Add a different server

Write a new section in the configuration file:

```toml
default_provider = "lmstudio"

[providers.myserver]
endpoint = "http://127.0.0.1:9000/v1"
api_key = ""        # empty means: read the key from the environment
lister = "openai"   # "openai" reads GET /v1/models; "lms" uses the lms command
```

An empty `api_key` makes milkwashy read `MYSERVER_API_KEY` from the environment or
from `.env`.

Then use it:

```bash
milkwashy models --provider myserver
milkwashy run --provider myserver --limit 3
```

The server must accept `POST /v1/chat/completions` and answer `GET /v1/models`.
