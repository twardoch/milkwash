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

<!-- daisyUI comes from a CDN as plain CSS. The components below need no build
     step, and the theme of this site keeps control of the page. -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5/daisyui.css">
<link rel="stylesheet" href="{{ '/assets/css/demo.css' | relative_url }}">

<div id="demo" class="milkwash-demo" data-theme="dark">

  <fieldset class="fieldset bg-base-200 border-base-300 rounded-box border p-4">
    <legend class="fieldset-legend">Source text</legend>

    <div class="demo-row">
      <label class="label" for="sample">Example text</label>
      <select id="sample" class="select select-bordered select-sm">
        <option value="en">English — rivers and machines</option>
        <option value="pl">Polish — rzeki i maszyny</option>
        <option value="de">German — Flüsse und Maschinen</option>
        <option value="ar">Arabic — الأنهار والآلات</option>
      </select>
      <label class="label" for="language">Language for the sentence search</label>
      <select id="language" class="select select-bordered select-sm">
        <option value="en">en</option>
        <option value="pl">pl</option>
        <option value="de">de</option>
        <option value="ar">ar</option>
      </select>
    </div>

    <textarea id="text" class="textarea textarea-bordered w-full" rows="10" spellcheck="false"></textarea>

    <div class="demo-row">
      <label class="label" for="minSent">Minimum sentences</label>
      <input id="minSent" type="number" class="input input-bordered input-sm demo-number" min="1" max="20" value="2">
      <label class="label" for="maxSent">Maximum sentences</label>
      <input id="maxSent" type="number" class="input input-bordered input-sm demo-number" min="1" max="40" value="8">
      <label class="label" for="maxChars">Character guard</label>
      <input id="maxChars" type="number" class="input input-bordered input-sm demo-number" min="50" max="20000" step="50" value="6000">
    </div>

    <div class="demo-row">
      <button id="run" type="button" class="btn btn-primary btn-sm" disabled>Make the plan</button>
      <button id="copy" type="button" class="btn btn-outline btn-sm" disabled>Copy the plan as JSON</button>
      <span id="status" role="status" class="badge badge-ghost badge-lg demo-status">The module loads now…</span>
    </div>
  </fieldset>

  <div class="stats stats-horizontal demo-stats" id="summary" hidden>
    <div class="stat"><div class="stat-title">Seed</div><div class="stat-value demo-stat-value" id="seed">—</div></div>
    <div class="stat"><div class="stat-title">Sentences</div><div class="stat-value demo-stat-value" id="sentenceCount">—</div></div>
    <div class="stat"><div class="stat-title">Chunks</div><div class="stat-value demo-stat-value" id="chunkCount">—</div></div>
    <div class="stat"><div class="stat-title">milkwashr</div><div class="stat-value demo-stat-value" id="version">—</div></div>
  </div>

  <div id="chunks" class="demo-chunks"></div>
</div>

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
