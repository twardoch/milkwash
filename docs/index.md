---
this_file: docs/index.md
title: Home
layout: default
nav_order: 1
---

# milkwash

Some systems put a statistical watermark into the text that a language model
writes. The watermark is a small change to the choice of words. A reader cannot
see it, but a detector can find it.

milkwash asks one question: **does a rephrase pass with a different language
model remove the watermark?**

milkwash gives you the equipment for the experiment. It does not give you the
answer. You run the sweep on your own models, and then you measure the result
with your own detector.

## What milkwash does

1. It cuts each source text into small parts. Each part has 2 to 8 sentences.
2. It sends each part to a language model with one of four rephrase prompts.
3. It puts the answers together again in the same order.
4. It repeats the run for each model that your local server can load.

The output is one text file for each model and each source text. You can then
give the original text and the rephrased text to a detector, and compare the
scores.

## The two packages

| Package | Language | Installation | Function |
|:--------|:---------|:-------------|:---------|
| [`milkwashr`](https://crates.io/crates/milkwashr) | Rust | `cargo add milkwashr` | It makes the chunk plan. It is also a Python extension module and a WebAssembly module. |
| [`milkwashy`](https://pypi.org/project/milkwashy/) | Python | `uv pip install milkwashy` | It finds the sentences, reads the configuration, speaks to the servers, and runs the sweep. |

`milkwashy` installs `milkwashr`. If you only want the chunk plan, install
`milkwashr` alone.

## Try it now

The [demonstration page](demo/) runs the real chunk code in your browser. The
page uses the WebAssembly build of `milkwashr`. Your text stays on your computer,
because the page sends nothing to a server.

## Why one seed controls everything

The seed comes from the text itself. It is the first 8 bytes of the BLAKE2b hash
of the text. The same text always gives the same seed, and the same seed always
gives the same chunks and the same prompts.

This rule is necessary. If two models receive different chunks, you cannot
compare their output. A difference in the score can then come from the chunks and
not from the model.

## Next steps

* [Install milkwash](install/)
* [Use the command line](cli/)
* [Connect a model server](providers/)
* [Try the browser demonstration](demo/)
* [Build and release milkwash](develop/)
