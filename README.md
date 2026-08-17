<!--
this_file: README.md
-->

# milkwash

**Does a rephrase pass with a language model remove a statistical watermark from a
text?**

Some systems put a watermark into the text that a language model writes. The
watermark is a small change to the choice of words. A reader cannot see it, but a
detector can find it. milkwash gives you the equipment to test if a rephrase pass
removes it.

Documentation and a browser demonstration: <https://twardoch.github.io/milkwash/>

milkwash does this work:

1. It cuts each source text into parts of 2 to 8 sentences.
2. It sends each part to a language model with one of four rephrase prompts.
3. It puts the answers together again in the same order.
4. It repeats the run for each model that your local server can load.

You then give the original text and the rephrased text to your detector, and you
compare the scores. milkwash makes the material for the experiment. It does not
measure the watermark.

## Two packages

| Package | Language | Install | Function |
|:--------|:---------|:--------|:---------|
| [`milkwashr`](https://crates.io/crates/milkwashr) | Rust | `cargo add milkwashr` | It makes the chunk plan. It is also a Python module and a WebAssembly module. |
| [`milkwashy`](https://pypi.org/project/milkwashy/) | Python | `uv pip install milkwashy` | It finds the sentences, reads the configuration, speaks to the servers, and runs the sweep. |

`milkwashy` installs `milkwashr`, so one command is sufficient:

```bash
uv pip install milkwashy
```

To build from this repository, and to install into your system Python:

```bash
./install.sh                   # or: ./install.sh --python /path/to/python3
```

For development:

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ./milkwashr -e ./milkwashy pytest
python -m pytest milkwashy/tests -q
```

## Use

```bash
milkwashy init_config       # write the TOML configuration file
milkwashy gen_indata        # write the four example texts to 01-indata/
milkwashy models            # list the models of the server
milkwashy plan              # show the chunks and the prompts; make no request
milkwashy lms_status        # show the LM Studio state
milkwashy lms_unload_all    # unload all models, and confirm it
milkwashy run --limit 5     # sweep the 5 smallest models
milkwashy run               # sweep all models; this takes hours
```

`run` accepts `--provider`, `--limit`, `--max_size_mb`, `--manage_lms` and
`--force`. Give `-- --help` to any command to see all of its flags.

To use all of the servers at the same time:

```bash
./sweep.sh                      # all servers, one process each
./sweep.sh --limit 5            # the 5 smallest models of each server
PROVIDERS="lmstudio" ./sweep.sh # one server only
PARALLEL=0 ./sweep.sh           # one server after the other
```

The servers do not compete for the same resource. Only LM Studio uses the memory
of the computer, because the other servers are remote. The total time is
therefore the time of the slowest server, and not the sum of all of them. A
measured example: 233 seconds together, against 347 seconds one after the other.

Each server writes its own log to `02-testllm/_logs/<server>.log`. A server that
does not answer is reported and skipped. It does not stop the other servers.

## How it works

**One seed controls the plan.** The seed is the first 8 bytes of the BLAKE2b hash
of the text. The same text always gives the same chunks and the same prompts. This
rule is necessary: if two models receive different chunks, a difference in the
score can come from the chunks and not from the model.

**Rust holds the plan, and only Rust.** `milkwashr` calculates the seed, makes the
chunks and selects the prompts. Python, Rust and the browser demonstration all
call the same code, so they cannot disagree. A test compares the WebAssembly
build with the Python build on five examples.

**The sentence search and the chunk assembly are separate.** `sentencex` (Python)
finds the sentence limits, because it has explicit support for Arabic and Polish.
`milkwashr` (Rust) then groups the sentences and applies `text-splitter` as a size
guard. A very long chunk cannot fill the context window of a small model.

**The loop puts the model outside and the text inside.** Each model is therefore
loaded one time in a sweep, and not one time for each chunk.

**One model only is in memory.** Each load goes through `lmsctl.load_exclusive`.
That function first proves with `lms ps --json` that the memory is empty. It
unloads what it finds, and it escalates to `lms unload --all`. If the memory is
still not empty, the sweep stops. The body of the loop is inside `try` and
`finally`, so the model leaves the memory after success, after a skip, after an
error and after Control-C. The check is at the load, not at the end of the loop:
every `continue`, every `break` and every error would be a way to load a second
model.

**Models are tested, not selected by name.** The model list of LM Studio also
holds embedding models, models that read images and other models that cannot
answer a chat request. milkwashy sends one short request of 8 tokens to each
model. A failure goes into `_skipped.json`, and the sweep continues.

**A sweep can continue.** If an output file is present, milkwashy makes no
request. If all of the outputs of a model are present, milkwashy does not load
that model. A model marked `load_failed` is not tried again, because bad tensors
do not repair themselves. A model marked `probe_failed` **is** tried again: a
server on the wrong port marks the complete list, and a permanent mark would then
make a corrected sweep report success with no output. `--force` ignores all of
these rules.

## The four prompts

1. Shorten the text by 10%, preserve the tone but use some synonyms
2. Expand the text by 10%, preserve the tone but use some synonyms
3. Preserve the text but use some synonyms
4. Rephrase this text to be more ASD-STE100

## Model servers

All of the requests use the OpenAI chat interface. The model list is different for
each server, so milkwashy reads it for each server: LM Studio comes from the `lms`
command, which is the only source with a size for each model. The other servers
answer `GET /v1/models`.

Each list is in the order `(size, name)`. Because of this, `--limit N` always
selects the same models. For CLIProxy, if the port in the configuration does not
answer a TCP connection, milkwashy tries the port minus 10000.

The settings come from the TOML file first, then from the environment (`.env` with
`python-dotenv`), then from the value in the program. See `.env.example`, and see
[Model servers](https://twardoch.github.io/milkwash/providers/).

## Development

```bash
./build.sh      # the gate: format, lint, test, wheels, Python tests, WASM parity
./wasm.sh       # build the WebAssembly module and compare it with Python
./install.sh    # install the built wheels into the system Python
./publish.sh    # a test run of a release
./publish.sh --real
```

`build.sh` fails if it changes any file in the repository. `publish.sh` needs a
clean `main` that is pushed. It writes one version into all of the manifests, it
makes one tag with `gitnextver`, and then it uploads: `milkwashr` to crates.io and
to PyPI, and then `milkwashy` to PyPI.

Run `./wasm.sh --refresh` after each change to the Rust code, and commit the new
module in `docs/assets/wasm/`. The documentation site serves that copy.

See [Build and release](https://twardoch.github.io/milkwash/develop/) for the
complete description.

## Files

```
milkwashr/       the Rust crate and the Python extension module
milkwashr-wasm/  the WebAssembly bindings
milkwashy/       the Python package
docs/            the documentation site and the prebuilt WebAssembly module
scripts/         version control for the manifests, and artifact inspection
tests/           the WebAssembly parity test
sweep.sh         all servers, at the same time
01-indata/       the source texts; git ignores them
02-testllm/      the output of the sweep; git ignores it
```

## Licence

Apache-2.0
