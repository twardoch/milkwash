<!--
this_file: README.md
-->

# milkwash

Does an LLM paraphrase pass wash a statistical text watermark out of a document?
`milkwash` builds the apparatus to find out: it takes long source texts, splits
them into 2–8 sentence chunks, rewrites every chunk through a randomly assigned
rephrase prompt, and repeats the whole run against every model a local
OpenAI-compatible server can serve.

Two packages:

- **`milkwashr`** — Rust extension (PyO3 + [`text-splitter`](https://crates.io/crates/text-splitter)):
  deterministic chunk assembly with a character-size guard.
  [crates.io](https://crates.io/crates/milkwashr) · [PyPI](https://pypi.org/project/milkwashr/)
- **`milkwashy`** — Python package with a Fire CLI: segmentation, config,
  providers, inference, and the sweep driver. [PyPI](https://pypi.org/project/milkwashy/)

## Install

From PyPI:

```bash
uv pip install milkwashy       # pulls milkwashr
```

From this checkout, into the interpreter uv treats as the system Python (so
`milkwashy` is on `PATH` everywhere):

```bash
./install.sh                   # or: ./install.sh --python /path/to/python3
```

For development:

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ./milkwashr -e ./milkwashy pytest
cp .env.example .env           # optional; LM Studio works without a key
```

## Use

```bash
milkwashy init_config       # TOML config under platformdirs
milkwashy gen_indata        # write the four seed texts to 01-indata/
milkwashy models            # list models (LM Studio via `lms`, others via /v1/models)
milkwashy plan              # show the chunk + prompt plan, no inference
milkwashy lms_status        # LM Studio server state + resident models
milkwashy lms_unload_all    # unload everything, verified
milkwashy run --limit 5     # sweep the 5 smallest models
milkwashy run               # full sweep (hours; resumable)
```

`run` accepts `--provider`, `--limit`, `--max_size_mb`, `--manage_lms`, and
`--force`.

To sweep every provider at once — LM Studio, CLIProxy and Chat2API run
**concurrently**, one process each:

```bash
./sweep.sh                      # everything, in parallel
./sweep.sh --limit 5            # 5 smallest models per provider
PROVIDERS="lmstudio" ./sweep.sh # one provider
PARALLEL=0 ./sweep.sh           # one at a time
```

They do not contend: outputs are grouped per provider, each writes its own log,
and only LM Studio touches local memory — the others are remote HTTP. Wall clock
is the slowest single provider rather than the sum (measured: 233 s parallel vs
347 s serial on a bounded run). LM Studio starts first because it is reliably the
longest leg.

Extra arguments are passed through to `milkwashy run`. Each provider logs to
`02-testllm/_logs/<provider>.log` — `tail -f` to watch. An unreachable provider
is reported and skipped rather than aborting the rest.

## How it works

**The chunk plan is computed once per source text, not once per model.** The
seed is `blake2b` of the text content, so chunk boundaries and prompt assignment
are identical for every model in the sweep — without that, no two models see the
same input and the outputs are not comparable. The plan is written next to each
output as `<text>.plan.json`.

**Segmentation and chunking are split deliberately.** `sentencex` (Python) finds
sentence boundaries — it has explicit Arabic and Polish support, where
unicode-segmentation-based splitters are weaker. `milkwashr` (Rust) groups those
sentences into 2–8 sentence chunks and applies `text-splitter` as a size guard so
an unusually long chunk cannot overflow a small model's context.

**The loop is model-outer, text-inner**, so each model is loaded and unloaded
once per sweep rather than once per chunk.

**Exactly one model is ever resident.** Every load goes through
`lmsctl.load_exclusive`, which first proves via `lms ps --json` that nothing is
loaded — unloading whatever it finds, escalating to `lms unload --all`, and
aborting the sweep if residency still cannot be proven empty. The per-model body
is wrapped in `try/finally`, so the model is unloaded and re-verified on success,
on skip, on error, and on interrupt. The check lives at the load site rather than
at the bottom of the loop because every `continue`, `break`, and exception path
would otherwise be a way to load a second model on top of the first. A model
whose outputs all exist already is not loaded at all.

**Models are probed, not filtered.** LM Studio's LLM list includes embedding
models, OCR models, vocoders, and other things that will not chat. Rather than
guessing from the name, each model gets one 8-token completion; failures are
recorded as `_skipped.json` and the sweep continues.

**Runs are resumable, and skipping existing output is the default.** Any
`(model, text)` whose output file already exists is left alone — no inference
call, and if *all* of a model's outputs exist it is never loaded. A model
recorded as `load_failed` is not retried either — bad tensors and unsupported
architectures do not fix themselves, and retrying costs a load on every later
sweep. A `probe_failed` model *is* retried, deliberately: a server on the wrong
port marks the entire catalogue `probe_failed`, and treating that as permanent
would make the corrected re-run skip everything and report success having
produced nothing. `--force` ignores all of it and rewrites. So an interrupted
multi-hour sweep finishes by re-running the same command.

## The four rephrase prompts

1. Shorten the text by 10%, preserve the tone but use some synonyms
2. Expand the text by 10%, preserve the tone but use some synonyms
3. Preserve the text but use some synonyms
4. Rephrase this text to be more ASD-STE100

## Providers

All inference goes through OpenAI-compatible endpoints. Model *listing* differs
per provider and is handled per provider: LM Studio is read from the `lms` CLI
(authoritative, and the only source with `sizeBytes` for the size ordering);
others use `GET /v1/models`. Every provider's list is ordered by
`(size_bytes, key)` — size first, key as tiebreak — so `--limit N` selects the
same N models on every run even where the API reports no size and no stable
order. For CLIProxy, if the configured port is not reachable, milkwashy retries
with `port - 10000` after an actual TCP connect test.

Configuration precedence: TOML config → environment (`.env` via python-dotenv) →
built-in default. See `.env.example`.

## Development

```bash
./build.sh      # fmt, clippy, cargo test, build both wheels, pytest, smoke
./install.sh    # install the built wheels into the system Python
./publish.sh    # dry run: full gates + predicted version
./publish.sh --real
```

`build.sh` fails if it modifies the checkout. `publish.sh` requires a clean,
pushed `main`; it syncs the version across manifests, tags once via
`gitnextver`, and only then uploads — `milkwashr` to crates.io and PyPI, then
`milkwashy` to PyPI.

## Layout

```
01-indata/     seed texts, generated (git-ignored)
02-testllm/    sweep outputs, generated (git-ignored)
milkwashr/     Rust extension crate
milkwashy/     Python package
scripts/       release version graph + artifact inspection
sweep.sh       all providers, concurrently
```

## License

Apache-2.0
