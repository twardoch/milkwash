---
this_file: docs/demo.md
title: Demonstration
layout: default
nav_order: 2
permalink: /demo/
---

# Chunk plan in your browser

This page runs the real `milkwashr` code. The code is a WebAssembly build of the
same Rust crate that the Python package uses.

The page does two things:

1. It finds the sentences with `Intl.Segmenter`, which your browser includes.
2. It sends the sentences to `milkwashr`, which makes the chunk plan.

Your text stays in your browser. The page sends no text to a server.

{: .warning }
> The module is 3.8 MB. The first use of the page must download it. Later visits
> use the copy in the browser cache.

{: .note }
> `milkwashy` finds the sentences with `sentencex`, not with `Intl.Segmenter`.
> The two libraries agree for most text. They can disagree at a difficult
> sentence limit, for example after an abbreviation. The chunk plan and the
> prompt choice are identical, because both use the same Rust code and the same
> seed.

<div id="demo" class="milkwash-demo">
  <div class="demo-row">
    <label for="sample">Example text</label>
    <select id="sample">
      <option value="en">English — rivers and machines</option>
      <option value="pl">Polish — rzeki i maszyny</option>
      <option value="de">German — Flüsse und Maschinen</option>
      <option value="ar">Arabic — الأنهار والآلات</option>
    </select>
    <label for="language">Language for the sentence search</label>
    <select id="language">
      <option value="en">en</option>
      <option value="pl">pl</option>
      <option value="de">de</option>
      <option value="ar">ar</option>
    </select>
  </div>

  <label for="text">Source text</label>
  <textarea id="text" rows="10" spellcheck="false"></textarea>

  <div class="demo-row">
    <label for="minSent">Minimum sentences</label>
    <input id="minSent" type="number" min="1" max="20" value="2">
    <label for="maxSent">Maximum sentences</label>
    <input id="maxSent" type="number" min="1" max="40" value="8">
    <label for="maxChars">Character guard</label>
    <input id="maxChars" type="number" min="50" max="20000" step="50" value="6000">
  </div>

  <div class="demo-row">
    <button id="run" type="button" disabled>Make the plan</button>
    <button id="copy" type="button" disabled>Copy the plan as JSON</button>
    <span id="status" role="status">The module loads now…</span>
  </div>

  <dl id="summary" class="demo-summary" hidden>
    <dt>Seed</dt><dd id="seed">—</dd>
    <dt>Sentences</dt><dd id="sentenceCount">—</dd>
    <dt>Chunks</dt><dd id="chunkCount">—</dd>
    <dt>milkwashr</dt><dd id="version">—</dd>
  </dl>

  <div id="chunks" class="demo-chunks"></div>
</div>

<link rel="stylesheet" href="{{ '/assets/css/demo.css' | relative_url }}">
<script type="module" src="{{ '/assets/js/demo.js' | relative_url }}"></script>

## What you see in the result

Each card in the result is one chunk. The card shows:

* the position of the chunk in the text;
* the sentences that the chunk holds;
* the prompt that this chunk receives;
* the number of characters in the chunk.

A sweep sends the chunk text and its prompt to the model. It then puts the
answers together in the same order.

## The four prompts

1. Shorten the text by 10%, preserve the tone but use some synonyms
2. Expand the text by 10%, preserve the tone but use some synonyms
3. Preserve the text but use some synonyms
4. Rephrase this text to be more ASD-STE100

The seed selects one prompt for each chunk. A different text gives a different
set of prompts, but the same text always gives the same set.

## Do the same work on your computer

```bash
uv pip install milkwashy
milkwashy gen_indata          # write the four example texts to 01-indata/
milkwashy plan                # show the same plan in your terminal
```

The `plan` command makes no request to a model. It only shows the chunks and the
prompts.
