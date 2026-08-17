<!--
this_file: CHANGELOG.md
-->

# Changelog

## Unreleased

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
