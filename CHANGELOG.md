<!--
this_file: CHANGELOG.md
-->

# Changelog

## Unreleased

### Added

- A WebAssembly build. `milkwashr-wasm` gives the chunk plan to a browser. The
  crate is not published, because a WebAssembly module has no use as a Rust
  dependency.
- A documentation site in `docs/`, for GitHub Pages with the Just the Docs theme.
  The theme loads from GitHub, and the repository holds no copy of it. The site
  holds a demonstration page that runs the prebuilt WebAssembly module.
- `./wasm.sh` builds the module and compares it with the Python module. The test
  uses five examples, and it compares the seed, the spans, the prompt choice and
  the chunk text. `./build.sh` runs the same test.
- `milkwashr` now gives `text_seed`, `prompt_index`, `prompts` and `PROMPTS` to
  Python. Rust holds the prompt list and the prompt choice, so Python, Rust and
  the browser cannot disagree.
- A server that only exists in the TOML file now reads `<NAME>_API_ENDPOINT` and
  `<NAME>_API_KEY`, the same as a built-in server.
- `milkwashy` exports `text_seed` and `segment_sentences`.

### Changed

- `milkwashr` is now two parts: `chunking.rs` holds the logic with no PyO3, and
  `python.rs` holds the bindings. The `python` feature controls the bindings, and
  it is on by default. Rust and WebAssembly users give
  `default-features = false`.
- `milkwashy.segment` calls Rust for the seed and for the prompt choice. Before
  this change, Python calculated the seed with `hashlib` and selected the prompt
  with `random.Random`. The prompt choice for a text is therefore different from
  version 1.0.0.
- `requires-python` for `milkwashy` is now `>=3.11`. `config.py` uses `tomllib`,
  and it raised an error on Python 3.10.
- All of the documentation uses ASD-STE100 Simplified Technical English.

## 1.0.0 — 2026-08-17

First public release of the two packages extracted from the private prototype.

### Added

- `milkwashr` — Rust crate and Python extension for deterministic sentence-chunk
  assembly with a `text-splitter` size guard. Published to crates.io and PyPI.
- `milkwashy` — Python package and Fire CLI: segmentation (`sentencex`), TOML
  config under `platformdirs`, provider discovery for LM Studio / CLIProxy /
  Chat2API, resumable model-outer sweep, and LM Studio residency control.
- `build.sh`, `install.sh`, `publish.sh` and `scripts/release-manifests.py`:
  one version number across every manifest, tag-driven releases via
  `gitnextver`, and a build that fails if it modifies the checkout.
- `sweep.sh` — runs every provider concurrently with a machine-wide lock around
  LM Studio sweeps.

### Changed from the prototype

- `milkwashr` is now built `abi3-py39`, so one wheel serves every CPython ≥ 3.9
  instead of requiring a rebuild per interpreter.
- `milkwashr` gained an `rlib` crate type and public Rust functions, making it a
  usable crates.io dependency rather than a Python-only artifact. The
  `pyo3/extension-module` feature is no longer a default — maturin enables it
  per build, which is what keeps `cargo build` and `cargo publish` working.
- Reference material, watermarking notes and experiment inputs/outputs stay in
  the private `_priv/` area and are not part of the published packages.
