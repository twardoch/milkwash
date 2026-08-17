// this_file: tests/wasm_parity.mjs
//
// Compares the WebAssembly build of milkwashr with the Python extension module.
//
// The Python side writes a reference file with the seed, the spans, the prompt
// choice and the chunk text for each example. This script gives the same
// sentences to the WebAssembly build and compares every value. If the two
// targets disagree, a browser and a sweep make different chunks, and then no
// result can be compared.
//
// Usage:
//   node tests/wasm_parity.mjs <path to the nodejs wasm-pack output> <reference.json>

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const [modulePath, referencePath] = process.argv.slice(2);
if (!modulePath || !referencePath) {
  console.error("usage: node tests/wasm_parity.mjs <wasm-dir> <reference.json>");
  process.exit(2);
}

const wasm = await import(pathToFileURL(`${modulePath}/milkwashr.js`).href);
const reference = JSON.parse(readFileSync(referencePath, "utf8"));

let checks = 0;
const failures = [];

function check(name, actual, expected) {
  checks += 1;
  const same = JSON.stringify(actual) === JSON.stringify(expected);
  if (!same) {
    failures.push(`${name}\n  wasm:   ${JSON.stringify(actual)}\n  python: ${JSON.stringify(expected)}`);
  }
}

check("ping", wasm.ping(), "milkwashr-ok");
check("prompts", wasm.prompts(), reference.prompts);
check("version", wasm.version(), reference.version);

for (const example of reference.examples) {
  const label = `${example.name} (${example.sentences.length} sentences)`;
  check(`${label} seed`, wasm.text_seed(example.joined), example.seed);

  const plan = wasm.plan(
    example.sentences,
    example.min_sent,
    example.max_sent,
    example.max_chars,
  );

  check(`${label} seed in plan`, plan.seed, example.seed);
  check(`${label} sentence count`, plan.sentence_count, example.sentences.length);
  check(`${label} chunk count`, plan.chunks.length, example.chunks.length);
  check(`${label} chunk text`, plan.chunks.map((c) => c.text), example.chunks.map((c) => c.text));
  check(
    `${label} prompt index`,
    plan.chunks.map((c) => c.prompt_index),
    example.chunks.map((c) => c.prompt_index),
  );
  check(
    `${label} spans`,
    plan.chunks.slice(0, example.spans.length).map((c) => [c.start, c.end]),
    example.spans,
  );

  // The size guard must hold.
  const tooLong = plan.chunks.filter((c) => c.characters > example.max_chars);
  check(`${label} size guard`, tooLong.length, 0);

  // No text may disappear. The guard can cut inside a sentence, and it then
  // removes the whitespace at the cut. Because of this, the comparison ignores
  // all whitespace.
  const squeeze = (value) => value.replace(/\s+/g, "");
  check(
    `${label} keeps all of the text`,
    squeeze(plan.chunks.map((c) => c.text).join("")),
    squeeze(example.sentences.join("")),
  );

  // If the guard cut nothing, every sentence must still appear complete.
  if (plan.chunks.length === example.spans.length) {
    const rebuilt = plan.chunks.map((c) => c.text).join(" ");
    check(
      `${label} keeps every sentence`,
      example.sentences.filter((s) => !rebuilt.includes(s)),
      [],
    );
  }
}

// A size-only split must respect the limit as well.
const pieces = wasm.split_by_size("Short sentence. ".repeat(120), 200);
check("split_by_size limit", pieces.filter((p) => p.length > 200).length, 0);
check("split_by_size is not empty", pieces.length > 1, true);

if (failures.length > 0) {
  console.error(`WASM PARITY FAILURE: ${failures.length} of ${checks} checks disagree\n`);
  for (const failure of failures) {
    console.error(failure);
  }
  process.exit(1);
}

console.log(`WASM parity passed: ${checks} checks over ${reference.examples.length} examples`);
