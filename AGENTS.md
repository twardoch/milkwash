# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Equipment for one experiment: does a rephrase pass with a language model remove a
statistical watermark from a text? The repository publishes three build products.

| Product | Language | Registry | Function |
|:--------|:---------|:---------|:---------|
| `milkwashr` | Rust (crate, and a PyO3 abi3-py39 module) | crates.io and PyPI | the chunk plan |
| `milkwashr-wasm` | Rust (WebAssembly) | none; `publish = false` | the same plan in a browser |
| `milkwashy` | Python (Fire command line) | PyPI | sentences, configuration, servers, sweep |

`milkwashy` pins `milkwashr` to the same version. The documentation site in
`docs/` holds a prebuilt copy of the WebAssembly module.

## Commands

```bash
./build.sh                   # the gate: fmt, clippy, cargo test, wheels, pytest, WASM parity
MILKWASH_SKIP_WASM=1 ./build.sh   # the same, without the WebAssembly step
./wasm.sh                    # build the WebAssembly module and compare it with Python
./wasm.sh --refresh          # the same, and write the module into docs/assets/wasm/
./install.sh                 # build the wheels and install them into uv's system Python
./publish.sh                 # a test run of a release
./publish.sh --real          # a release; it cannot be undone
```

Narrow loops while you work:

```bash
cargo test --workspace
cargo test -p milkwashr --doc
cargo build -p milkwashr --no-default-features     # the form that Rust and WASM users get
cargo clippy --all-targets --no-deps -- -D warnings
cargo fmt --all

uv pip install -e ./milkwashr -e ./milkwashy pytest
python -m pytest milkwashy/tests -q
python -m pytest milkwashy/tests/test_rust_agreement.py -q
python -m pytest milkwashy/tests/test_resume.py::test_second_run_skips_existing_outputs -q
node tests/wasm_parity.mjs <wasm-pack nodejs output dir> <reference.json>
```

`build.sh` fails if it changes any tracked file. The release depends on that
property, because the release runs the build two times and compares the tree.

## Architecture

**One seed controls the plan.** The seed is the first 8 bytes of the BLAKE2b hash
of the text, read as a big-endian integer. It selects the chunk limits and the
prompt for each chunk. Every model in a sweep must receive identical chunks.
Without that, a difference in a watermark score can come from the chunks.
Therefore: never make the chunk plan depend on the model, the time, or the
position of a file.

**Rust holds the plan, and Python must not repeat it.**
`milkwashr/src/chunking.rs` holds the seed calculation, the random number
generator, the chunk spans, the size guard, the prompt list and the prompt choice.
`milkwashr/src/python.rs` and `milkwashr-wasm/src/lib.rs` only change types.
`milkwashy/segment.py` calls `milkwashr.text_seed` and
`milkwashr.prompt_index`; it does not calculate them. `test_rust_agreement.py`
holds that rule in place.

**The crate must build without PyO3.** The `python` feature is on by default,
because maturin builds the wheel from that manifest. Rust users and the
WebAssembly build use `default-features = false`. `pyo3/extension-module` must
stay out of the default features: as a default it breaks `cargo build`,
`cargo test` and `cargo publish`.

**The sentence search stays in Python.** `sentencex` finds the sentence limits,
because it has explicit support for Arabic and Polish. Do not move that work into
Rust. The browser demonstration uses `Intl.Segmenter` instead, which can find
different limits in difficult text. The chunk plan for a given sentence list is
identical in all three targets, and the parity test proves it.

**The sweep loop puts the model outside and the text inside**
(`milkwashy/pipeline.py`). Each model therefore loads one time for each sweep.

**One LM Studio model only is in memory.** `lmsctl.load_exclusive` proves with
`lms ps --json` that the memory is empty before it loads. The body of the loop is
inside `try` and `finally`. The check is at the load, not at the end of the loop,
because every `continue`, every `break` and every error would be a way to load a
second model. Keep that arrangement.

**The rules for a continued sweep are not symmetrical, and that is deliberate.**
An existing output file means skip. `load_failed` is permanent, because bad
tensors do not repair themselves. `probe_failed` is temporary, because a server on
the wrong port marks the complete model list; a permanent mark would make a
corrected sweep report success with no output. `--force` ignores all of it.

**The model list is per server, the requests are not.** All requests use the
OpenAI chat interface. LM Studio gives its list through the `lms` command, which
is the only source with a size for each model. The other servers answer
`GET /v1/models`. Each list is in the order `(size, name)`, so `--limit N` is
stable. CLIProxy falls back to the port minus 10000 after a real TCP test.

Settings come from the TOML file, then the environment, then the program. A server
that only exists in the TOML file reads `<NAME>_API_ENDPOINT` and
`<NAME>_API_KEY`, the same as a built-in server.

**`milkwashy` needs Python 3.11.** `config.py` uses `tomllib`, and it raises an
error on an older version. `requires-python` must agree with that check.

## The WebAssembly module and the site

`docs/` is a Jekyll site for GitHub Pages. It loads the Just the Docs theme from
GitHub with `remote_theme`, so the repository holds no copy of the theme.

`docs/assets/wasm/` holds the prebuilt module, and `docs/assets/wasm/VERSION` holds
its version. `build.sh` compares that version with the manifests and fails if they
differ. `./wasm.sh --refresh` writes a new module; commit the result. The site has
no build step of its own for the module.

`docs/assets/js/samples.js` comes from `milkwashy/src/milkwashy/indata.py`. Do not
edit it by hand. Generate it again if the example texts change.

The WebAssembly build needs `rustup target add wasm32-unknown-unknown`, `wasm-pack`
and `node`. `.cargo/config.toml` gives `getrandom` the `wasm_js` backend; without
that flag the build stops, because `ahash` below `text-splitter` needs a source of
random numbers.

## Release mechanics

The **git tag is the only source of the version number**.
`scripts/release-manifests.py` is the only program that may change a version in a
tracked file. It keeps `milkwashr/Cargo.toml`, `milkwashr-wasm/Cargo.toml` (and its
pin), `milkwashy/pyproject.toml` (and its pin) and `milkwashy/__init__.py`
identical. Each version site must match exactly one line, so a manifest must not
hold a second line that starts with `version = `.

`publish.sh` holds these rules:

- branch `main`, upstream `origin/main`, a remote that is not in front, no conflicts
- the next version follows `gitnextver`: the highest `v` tag plus one patch, or
  `1.0.0` when the repository has no tag
- the gates run at the current version; then the manifests move to the target
  version; then `build.sh` runs again. A change outside the allowlist stops the
  release.
- `uvx gitnextver@1.0.1` makes the one commit, the one tag and the one push. It
  makes a tag only when the repository has a change to commit, and the version
  change is that change. Do not commit the version change yourself.
- the uploads are last and in order: crates.io `milkwashr`, PyPI `milkwashr`, PyPI
  `milkwashy`. The script waits for each registry.

`CARGO_REGISTRY_TOKEN` and `UV_PUBLISH_TOKEN` are necessary for `--real`.

A test of the target version before a real release is cheap and it prevents a
pushed tag with a broken artifact: clone the repository into a temporary
directory, tag it, run `sync`, commit, and then run `build.sh`.

## Style rules for this repository

- Prose in Markdown files uses ASD-STE100 Simplified Technical English: short
  sentences, the active voice, one instruction in one sentence, and no idiom.
- Every source file holds a `this_file:` line near the top. Update it when you
  move a file.
- Test names use `test_<unit>_when_<condition>_then_<result>`, or a plain
  description for a test with fixtures.
- Tests must not need a network, a model server, or model weights.

## `_priv/` is private

`_priv/` holds the first prototype, reference material and experiment data. Git
ignores it. Do not copy these into the public tree: `_priv/**/ref/` (other
people's licences), `_priv/**/issues/` (fragments of API keys),
`_priv/**/01-indata`, `_priv/**/02-testllm`, and `WORK.md`. The example texts are
in `milkwashy/indata.py`, and `milkwashy gen_indata` writes them again.
