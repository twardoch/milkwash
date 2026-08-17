//! this_file: milkwashr-wasm/src/lib.rs
//!
//! WebAssembly bindings for `milkwashr`.
//!
//! These functions call the same code as the Python extension module. A browser
//! and a sweep on your computer make the same plan for the same text.
//!
//! The browser must find the sentences before it calls `plan`. The demonstration
//! page uses `Intl.Segmenter`, which all current browsers include. `milkwashy`
//! uses `sentencex` instead, and the two libraries can find different sentence
//! limits in difficult text.

use serde::Serialize;
use wasm_bindgen::prelude::*;

/// One chunk of a plan.
#[derive(Serialize)]
pub struct Chunk {
    /// Position of the chunk in the text. The first chunk is 0.
    pub index: usize,
    /// Position of the first sentence of the chunk in the sentence list.
    pub start: usize,
    /// Position after the last sentence of the chunk.
    pub end: usize,
    /// Number of sentences in the chunk.
    pub sentences: usize,
    /// Number of characters in the chunk text.
    pub characters: usize,
    /// The chunk text.
    pub text: String,
    /// Position of the prompt in the prompt list.
    pub prompt_index: usize,
    /// The prompt for this chunk.
    pub prompt: String,
}

/// A complete plan for one text.
#[derive(Serialize)]
pub struct Plan {
    /// The seed, as a decimal string. JavaScript numbers cannot hold 64 bits.
    pub seed: String,
    /// Number of sentences that the plan received.
    pub sentence_count: usize,
    /// The chunks, in text order.
    pub chunks: Vec<Chunk>,
}

/// Gives the version of the crate that built this module.
#[wasm_bindgen]
pub fn version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// Tells you that the module is loaded and can run.
#[wasm_bindgen]
pub fn ping() -> String {
    "milkwashr-ok".to_string()
}

/// Gives the four rephrase prompts, in index order.
#[wasm_bindgen]
pub fn prompts() -> Vec<String> {
    milkwashr::PROMPTS.iter().map(|p| p.to_string()).collect()
}

/// Gives the seed of a text, as a decimal string.
#[wasm_bindgen]
pub fn text_seed(text: &str) -> String {
    milkwashr::text_seed(text).to_string()
}

/// Makes a complete plan from sentences that are already separated.
///
/// `sentences` must hold one sentence in each item. The function returns a
/// `Plan` object. If a chunk is longer than `max_chars` characters, the size
/// guard cuts it, and then the chunk count is more than the span count.
#[wasm_bindgen]
pub fn plan(
    sentences: Vec<String>,
    min_sent: usize,
    max_sent: usize,
    max_chars: usize,
) -> Result<JsValue, JsValue> {
    let joined = sentences.join(" ");
    let seed = milkwashr::text_seed(&joined);
    let texts = milkwashr::assemble_chunks(&sentences, seed, min_sent, max_sent, max_chars);
    let spans = milkwashr::plan_chunk_spans(sentences.len(), seed, min_sent, max_sent);

    let mut chunks = Vec::with_capacity(texts.len());
    for (index, text) in texts.into_iter().enumerate() {
        // The size guard can make more chunks than spans. In that case the
        // extra chunks keep the span of the last known group.
        let (start, end) = spans.get(index).copied().unwrap_or_else(|| {
            spans
                .last()
                .copied()
                .unwrap_or((sentences.len(), sentences.len()))
        });
        let prompt_index = milkwashr::prompt_index(seed, index);
        chunks.push(Chunk {
            index,
            start,
            end,
            sentences: end.saturating_sub(start),
            characters: text.chars().count(),
            text,
            prompt_index,
            prompt: milkwashr::PROMPTS[prompt_index].to_string(),
        });
    }

    let plan = Plan {
        seed: seed.to_string(),
        sentence_count: sentences.len(),
        chunks,
    };
    serde_wasm_bindgen::to_value(&plan).map_err(|error| JsValue::from_str(&error.to_string()))
}

/// Cuts a text by size only. Use this when the sentences are not available.
#[wasm_bindgen]
pub fn split_by_size(text: &str, max_chars: usize) -> Vec<String> {
    milkwashr::split_by_size(text, max_chars)
}
