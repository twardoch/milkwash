//! this_file: milkwashr/src/lib.rs
//! Rust-backed chunk assembly for the milkwash pipeline.
//!
//! Sentence *segmentation* is done in Python (sentencex, strong multilingual /
//! Arabic / Polish support). This crate does deterministic *chunk assembly*:
//! group 2-8 sentences per chunk with a per-text seeded RNG, and use the
//! `text-splitter` crate as a size guard so an over-long chunk cannot blow a
//! model's context window.

use pyo3::prelude::*;
use text_splitter::{ChunkConfig, TextSplitter};

/// Tiny deterministic RNG (xorshift64*). Seeded per source text so every model
/// in the sweep replays the identical chunk plan.
struct XorShift64 {
    state: u64,
}

impl XorShift64 {
    fn new(seed: u64) -> Self {
        // Avoid the zero fixed-point.
        XorShift64 {
            state: if seed == 0 { 0x9E3779B97F4A7C15 } else { seed },
        }
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        x.wrapping_mul(0x2545F4914F6CDD1D)
    }

    /// Uniform integer in [lo, hi] inclusive.
    fn range_inclusive(&mut self, lo: usize, hi: usize) -> usize {
        if hi <= lo {
            return lo;
        }
        let span = (hi - lo + 1) as u64;
        lo + (self.next_u64() % span) as usize
    }
}

/// Sanity ping — proves the extension built and imports.
#[pyfunction]
pub fn ping() -> &'static str {
    "milkwashr-ok"
}

/// Group sentence indices into chunks of `min_sent..=max_sent` sentences.
///
/// Returns a list of (start, end) *half-open* index ranges over the input
/// sentence list, produced by a seed-deterministic RNG.
#[pyfunction]
#[pyo3(signature = (n_sentences, seed, min_sent=2, max_sent=8))]
pub fn plan_chunk_spans(
    n_sentences: usize,
    seed: u64,
    min_sent: usize,
    max_sent: usize,
) -> Vec<(usize, usize)> {
    let mut rng = XorShift64::new(seed);
    let mut spans = Vec::new();
    let mut i = 0usize;
    while i < n_sentences {
        let want = rng.range_inclusive(min_sent.max(1), max_sent.max(min_sent.max(1)));
        let end = (i + want).min(n_sentences);
        spans.push((i, end));
        i = end;
    }
    spans
}

/// Assemble chunk strings from pre-segmented `sentences`.
///
/// Groups 2-8 sentences (seed-deterministic), joins with a space, then applies
/// `text-splitter` as a size guard: any assembled chunk longer than
/// `max_chars` characters is split into <= `max_chars` pieces so it stays
/// inside the model context. Order is preserved.
#[pyfunction]
#[pyo3(signature = (sentences, seed, min_sent=2, max_sent=8, max_chars=6000))]
pub fn assemble_chunks(
    sentences: Vec<String>,
    seed: u64,
    min_sent: usize,
    max_sent: usize,
    max_chars: usize,
) -> PyResult<Vec<String>> {
    let spans = plan_chunk_spans(sentences.len(), seed, min_sent, max_sent);
    let splitter = TextSplitter::new(ChunkConfig::new(max_chars));
    let mut out = Vec::new();
    for (start, end) in spans {
        let joined = sentences[start..end].join(" ");
        if joined.chars().count() <= max_chars {
            out.push(joined);
        } else {
            for piece in splitter.chunks(&joined) {
                out.push(piece.to_string());
            }
        }
    }
    Ok(out)
}

/// Split raw text purely by size using text-splitter (helper / fallback).
#[pyfunction]
#[pyo3(signature = (text, max_chars=6000))]
pub fn split_by_size(text: &str, max_chars: usize) -> Vec<String> {
    let splitter = TextSplitter::new(ChunkConfig::new(max_chars));
    splitter.chunks(text).map(|c| c.to_string()).collect()
}

#[pymodule]
fn milkwashr(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    m.add_function(wrap_pyfunction!(plan_chunk_spans, m)?)?;
    m.add_function(wrap_pyfunction!(assemble_chunks, m)?)?;
    m.add_function(wrap_pyfunction!(split_by_size, m)?)?;
    Ok(())
}
