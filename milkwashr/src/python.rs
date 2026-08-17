//! this_file: milkwashr/src/python.rs
//!
//! Python bindings. This file only changes types. All of the logic is in
//! `chunking.rs`, and the WebAssembly bindings use the same functions.

use pyo3::prelude::*;

use crate::chunking;

/// Tells you that the extension module is built and can be imported.
#[pyfunction]
fn ping() -> &'static str {
    "milkwashr-ok"
}

/// Gives the 64-bit seed for a text.
#[pyfunction]
#[pyo3(signature = (text))]
fn text_seed(text: &str) -> u64 {
    chunking::text_seed(text)
}

/// Gives the prompt index for one chunk of a text.
#[pyfunction]
#[pyo3(signature = (seed, index))]
fn prompt_index(seed: u64, index: usize) -> usize {
    chunking::prompt_index(seed, index)
}

/// Gives the four rephrase prompts, in index order.
#[pyfunction]
fn prompts() -> Vec<&'static str> {
    chunking::PROMPTS.to_vec()
}

/// Groups sentence positions into chunks of 2 to 8 sentences.
#[pyfunction]
#[pyo3(signature = (n_sentences, seed, min_sent=2, max_sent=8))]
fn plan_chunk_spans(
    n_sentences: usize,
    seed: u64,
    min_sent: usize,
    max_sent: usize,
) -> Vec<(usize, usize)> {
    chunking::plan_chunk_spans(n_sentences, seed, min_sent, max_sent)
}

/// Builds chunk texts from sentences that are already separated.
#[pyfunction]
#[pyo3(signature = (sentences, seed, min_sent=2, max_sent=8, max_chars=6000))]
fn assemble_chunks(
    sentences: Vec<String>,
    seed: u64,
    min_sent: usize,
    max_sent: usize,
    max_chars: usize,
) -> Vec<String> {
    chunking::assemble_chunks(&sentences, seed, min_sent, max_sent, max_chars)
}

/// Cuts a text by size only.
#[pyfunction]
#[pyo3(signature = (text, max_chars=6000))]
fn split_by_size(text: &str, max_chars: usize) -> Vec<String> {
    chunking::split_by_size(text, max_chars)
}

#[pymodule]
fn milkwashr(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PROMPTS", chunking::PROMPTS.to_vec())?;
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    m.add_function(wrap_pyfunction!(text_seed, m)?)?;
    m.add_function(wrap_pyfunction!(prompt_index, m)?)?;
    m.add_function(wrap_pyfunction!(prompts, m)?)?;
    m.add_function(wrap_pyfunction!(plan_chunk_spans, m)?)?;
    m.add_function(wrap_pyfunction!(assemble_chunks, m)?)?;
    m.add_function(wrap_pyfunction!(split_by_size, m)?)?;
    Ok(())
}
