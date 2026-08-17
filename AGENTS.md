# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

An experiment apparatus: does an LLM paraphrase pass wash a statistical text
watermark out of a document? Two published packages implement it.

| Package | Language | Registries | Role |
| --- | --- | --- | --- |
| `milkwashr` | Rust (PyO3, abi3-py39) | crates.io + PyPI | deterministic chunk assembly, `text-splitter` size guard |
| `milkwashy` | Python (Fire CLI) | PyPI | segmentation, config, providers, inference, sweep driver |

`milkwashy` imports `milkwashr` and pins it to the exact same version.

## Commands

```bash
./build.sh                  # the gate: fmt, clippy, cargo test, both wheels, pytest, smoke
./install.sh                # build wheels and install into uv's system Python
./install.sh --python PATH  # ... into a specific interpreter
./publish.sh                # dry run: preflight + all gates + predicted version
./publish.sh --real         # irreversible: tag, push, upload to crates.io + PyPI
```

Narrower loops while iterating:

```bash
cargo test --workspace
cargo clippy --all-targets --no-deps -- -D warnings
uv pip install -e ./milkwashr -e ./milkwashy pytest    # editable dev install
python -m pytest milkwashy/tests -q
python -m pytest milkwashy/tests/test_resume.py::test_second_run_skips_existing_outputs -q
```

`build.sh` fails if it leaves the checkout modified — that check exists because
the release flow depends on the build being a pure function of the tree. If it
trips, something wrote into a tracked path.

## Architecture

**The chunk plan is content-seeded and computed once per source text.** `blake2b`
of the text gives the seed; `milkwashr` derives chunk spans from it and
`milkwashy` derives prompt assignment from it. Every model in a sweep therefore
sees identical chunks with identical prompts — that comparability is the entire
point of the experiment, so nothing may make chunking depend on the model.

**Segmentation and chunking live on opposite sides of the FFI boundary on
purpose.** `sentencex` (Python) finds sentence boundaries because it has explicit
Arabic and Polish support; `milkwashr` (Rust) groups sentences into 2–8 sentence
chunks and applies `text-splitter` only as a size guard. Do not move sentence
segmentation into Rust.

**The sweep loop is model-outer, text-inner** (`milkwashy/pipeline.py`), so each
model loads and unloads once per sweep rather than once per chunk.

**Exactly one LM Studio model is ever resident.** `lmsctl.load_exclusive` proves
via `lms ps --json` that nothing is loaded before loading, and the per-model body
is wrapped in `try/finally`. The check sits at the load site rather than at the
end of the loop because every `continue`, `break`, and exception path would
otherwise be a way to stack a second model on the first. Preserve that invariant.

**Resume semantics are asymmetric on purpose.** An existing output file means
skip; `load_failed` is permanent (bad tensors do not fix themselves);
`probe_failed` is retried (a server on the wrong port marks the whole catalogue
`probe_failed`, and treating that as permanent would make a corrected re-run
report success having produced nothing). `--force` overrides everything.

**Provider listing differs per provider, inference does not.** All inference goes
through OpenAI-compatible endpoints. LM Studio's model list comes from the `lms`
CLI (the only source with `sizeBytes`); the others use `GET /v1/models`. Lists
are ordered by `(size_bytes, key)` so `--limit N` is stable. CLIProxy falls back
to `port - 10000` after a real TCP connect test.

Config precedence: TOML under `platformdirs` → `.env` → built-in default.

## Release mechanics

The **git tag is the single source of truth** for the version.
`scripts/release-manifests.py` is the only thing allowed to move version numbers
in tracked files; it keeps `milkwashr/Cargo.toml`, `milkwashy/pyproject.toml`
(both its own version and the `milkwashr==` pin) and `milkwashy/__init__.py`
identical. `publish.sh` enforces the interesting parts:

- branch `main`, upstream `origin/main`, remote not ahead, no unresolved conflicts
- next version mirrors `gitnextver`: highest `v*` tag plus one patch, or `1.0.0`
  when no tags exist
- gates run at the *current* version, then manifests sync to the *target*
  version, then `build.sh` runs again; a diff outside the manifest allowlist aborts
- `uvx gitnextver@1.0.1` makes the single commit + tag + push. It only tags when
  the tree is dirty, which the manifest sync guarantees — do not "helpfully"
  commit the sync yourself, or nothing gets tagged
- uploads last, in dependency order: crates.io `milkwashr`, PyPI `milkwashr`,
  PyPI `milkwashy`, each waited on until the registry serves it

`CARGO_REGISTRY_TOKEN` and `UV_PUBLISH_TOKEN` are required for `--real`.

## Conventions

- Every source file carries a `this_file:` path record near the top — a comment
  in code, YAML front matter in Markdown. Update it when moving files.
- `pyo3/extension-module` is **not** a default Cargo feature. maturin enables it
  per build (`[tool.maturin] features`). Enabling it in `Cargo.toml` breaks
  `cargo build`, `cargo test` and `cargo publish` verification.
- `milkwashr` is `abi3-py39`: one wheel serves every CPython ≥ 3.9. Keep it that
  way; the release publishes from one machine.
- Unit tests prefer the `test_<unit>_when_<condition>_then_<result>` form
  (`test_milkwashy.py`); fixture-driven behaviour tests use plainer names
  (`test_resume.py`). Either way tests must not need a network or a running LM
  Studio — the suite monkeypatches `subprocess` and `httpx`.

## `_priv/` is private and stays private

`_priv/` holds the original prototype, reference material and experiment data. It
is git-ignored and nothing in it is published. Specifically **do not** port to
the public tree: `_priv/**/ref/` (third-party reference material, including
`synthid-text`, under its own licenses), `_priv/**/issues/` (contains API key
fragments), `_priv/**/01-indata` and `_priv/**/02-testllm` (experiment inputs and
outputs — `milkwashy gen_indata` regenerates the seed texts, which are authored
inline in `milkwashy/indata.py`), and `WORK.md`.

`.env` is ignored; `.env.example` carries `REPLACE_ME` placeholders only.
