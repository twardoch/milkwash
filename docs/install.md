---
this_file: docs/install.md
title: Installation
layout: default
nav_order: 3
permalink: /install/
---

# Installation

## From PyPI

This is the usual method. It gives you the `milkwashy` command and the
`milkwashr` extension module.

```bash
uv pip install milkwashy
```

`pip install milkwashy` also works. The wheel for `milkwashr` needs no compiler,
because one wheel serves all CPython versions from 3.9.

Make sure that the installation works:

```bash
milkwashy config
python -c "import milkwashr; print(milkwashr.ping())"
```

The second command must print `milkwashr-ok`.

## Only the chunk code

Install `milkwashr` alone if you do not need the sweep:

```bash
uv pip install milkwashr        # Python
cargo add milkwashr             # Rust
```

For Rust, switch off the default features. This removes PyO3 from your build:

```toml
[dependencies]
milkwashr = { version = "1", default-features = false }
```

## From this repository

The script builds both wheels and installs them into the interpreter that `uv`
finds as the system Python. The `milkwashy` command is then on your `PATH`.

```bash
git clone https://github.com/twardoch/milkwash
cd milkwash
./install.sh
```

To use a different interpreter, name it:

```bash
./install.sh --python /opt/homebrew/bin/python3.12
```

The script tests the wheels in a temporary environment before it installs them.
It also makes sure that it changes no file in the repository.

## For development

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ./milkwashr -e ./milkwashy pytest
python -m pytest milkwashy/tests -q
```

## Configuration

Write the configuration file, and then look at it:

```bash
milkwashy init_config     # writes the file and prints its location
milkwashy config          # prints the values in use
```

The file is TOML, and `platformdirs` decides its location. On macOS the location
is `~/Library/Application Support/milkwashy/config.toml`. On Linux it is
`~/.config/milkwashy/config.toml`.

Copy the example environment file if your servers need a key:

```bash
cp .env.example .env
```

LM Studio needs no key. See [Model servers](../providers/) for the details.

## What you need for a sweep

* A server with an OpenAI-compatible interface. LM Studio is the default.
* Source texts. `milkwashy gen_indata` writes four example texts.
* Time. A complete sweep over many models takes hours. You can stop it and start
  it again, because the sweep continues where it stopped.
