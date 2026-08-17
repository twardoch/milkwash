// this_file: docs/assets/js/demo.js
//
// The browser demonstration of the milkwashr chunk plan.
//
// The page finds the sentences with Intl.Segmenter, and then gives them to the
// WebAssembly build of milkwashr. All of the chunk logic stays in Rust, so the
// browser and a sweep on your computer make the same plan.

import init, { plan, prompts, ping, version } from "../wasm/milkwashr.js";
import { SAMPLES } from "./samples.js";

const element = (id) => document.getElementById(id);
const ui = {
  sample: element("sample"),
  language: element("language"),
  text: element("text"),
  minSent: element("minSent"),
  maxSent: element("maxSent"),
  maxChars: element("maxChars"),
  run: element("run"),
  copy: element("copy"),
  status: element("status"),
  summary: element("summary"),
  seed: element("seed"),
  sentenceCount: element("sentenceCount"),
  chunkCount: element("chunkCount"),
  version: element("version"),
  chunks: element("chunks"),
};

let lastPlan = null;

function say(message, kind = "info") {
  ui.status.textContent = message;
  ui.status.dataset.kind = kind;
}

// Intl.Segmenter gives the sentence limits. Empty results fall back to the
// complete text, which is what milkwashy does as well.
function findSentences(text, language) {
  const trimmed = text.trim();
  if (trimmed === "") {
    return [];
  }
  if (typeof Intl === "undefined" || typeof Intl.Segmenter !== "function") {
    return [trimmed];
  }
  const segmenter = new Intl.Segmenter(language, { granularity: "sentence" });
  const sentences = [];
  for (const part of segmenter.segment(trimmed)) {
    const sentence = part.segment.trim();
    if (sentence !== "") {
      sentences.push(sentence);
    }
  }
  return sentences.length > 0 ? sentences : [trimmed];
}

function readLimits() {
  const min = Math.max(1, Number.parseInt(ui.minSent.value, 10) || 1);
  const max = Math.max(min, Number.parseInt(ui.maxSent.value, 10) || min);
  const chars = Math.max(50, Number.parseInt(ui.maxChars.value, 10) || 6000);
  // Show the correction, so the numbers on the page match the numbers in use.
  ui.minSent.value = String(min);
  ui.maxSent.value = String(max);
  ui.maxChars.value = String(chars);
  return { min, max, chars };
}

function render(result) {
  ui.seed.textContent = result.seed;
  ui.sentenceCount.textContent = String(result.sentence_count);
  ui.chunkCount.textContent = String(result.chunks.length);
  ui.summary.hidden = false;

  ui.chunks.replaceChildren(
    ...result.chunks.map((chunk) => {
      const card = document.createElement("article");
      card.className = "chunk card bg-base-200 card-border border-base-300 card-sm";
      const body = document.createElement("div");
      body.className = "card-body";

      const head = document.createElement("div");
      head.className = "demo-row";
      const position = document.createElement("span");
      position.className = "badge badge-primary badge-sm";
      position.textContent = `Chunk ${chunk.index + 1}`;
      const facts = document.createElement("span");
      facts.className = "chunk-facts";
      facts.textContent =
        `sentences ${chunk.start + 1}–${chunk.end} · ` +
        `${chunk.sentences} sentence${chunk.sentences === 1 ? "" : "s"} · ` +
        `${chunk.characters} characters`;
      head.append(position, facts);

      const prompt = document.createElement("p");
      prompt.className = "chunk-prompt";
      prompt.textContent = `Prompt ${chunk.prompt_index + 1}: ${chunk.prompt}`;

      const text = document.createElement("p");
      text.className = "chunk-text";
      text.textContent = chunk.text;

      body.append(head, prompt, text);
      card.append(body);
      return card;
    }),
  );
}

function run() {
  const { min, max, chars } = readLimits();
  const sentences = findSentences(ui.text.value, ui.language.value);
  if (sentences.length === 0) {
    say("Write some text first.", "error");
    return;
  }
  try {
    const result = plan(sentences, min, max, chars);
    lastPlan = result;
    render(result);
    ui.copy.disabled = false;
    say(`${result.chunks.length} chunks from ${sentences.length} sentences.`, "ok");
  } catch (error) {
    say(`The plan failed: ${error}`, "error");
  }
}

function loadSample() {
  const code = ui.sample.value;
  const sample = SAMPLES[code];
  if (sample) {
    ui.text.value = sample.text;
    ui.language.value = code;
  }
}

async function copyPlan() {
  if (lastPlan === null) {
    return;
  }
  const json = JSON.stringify(lastPlan, null, 2);
  try {
    await navigator.clipboard.writeText(json);
    say("The plan is on the clipboard.", "ok");
  } catch {
    // Some browsers refuse the clipboard without a permission. Show the JSON
    // instead, because the user can then copy it manually.
    const box = document.createElement("pre");
    box.className = "chunk-json mockup-code";
    box.textContent = json;
    ui.chunks.prepend(box);
    say("The browser refused the clipboard. The JSON is at the top.", "error");
  }
}

async function start() {
  loadSample();
  try {
    await init(new URL("../wasm/milkwashr_bg.wasm", import.meta.url));
  } catch (error) {
    say(`The module did not load: ${error}`, "error");
    return;
  }
  if (ping() !== "milkwashr-ok") {
    say("The module loaded, but it does not answer correctly.", "error");
    return;
  }
  ui.version.textContent = version();
  ui.run.disabled = false;
  say(`Ready. ${prompts().length} prompts are available.`, "ok");
  run();
}

ui.run.addEventListener("click", run);
ui.copy.addEventListener("click", copyPlan);
ui.sample.addEventListener("change", () => {
  loadSample();
  run();
});

start();
