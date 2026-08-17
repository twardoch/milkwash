//! this_file: milkwashr/src/lib.rs
//!
//! Deterministic chunk assembly for the milkwash pipeline.
//!
//! Sentence segmentation happens before this crate runs. In `milkwashy`,
//! `sentencex` does it, because that library gives good results for Arabic and
//! Polish. This crate then groups the sentences into chunks of 2 to 8
//! sentences, and uses `text-splitter` as a size guard.
//!
//! One seed controls the result. The seed comes from the text itself, so all of
//! the models in a sweep get identical chunks. If the chunks are not identical,
//! you cannot compare the outputs.
//!
//! ```
//! let seed = milkwashr::text_seed("Rivers move. Machines stop. People wait.");
//! let sentences: Vec<String> = ["Rivers move.", "Machines stop.", "People wait."]
//!     .iter()
//!     .map(|s| s.to_string())
//!     .collect();
//! let chunks = milkwashr::assemble_chunks(&sentences, seed, 2, 8, 6000);
//! assert_eq!(chunks.join(" ").matches("Rivers move.").count(), 1);
//! ```
//!
//! Three targets use this crate:
//!
//! * Rust programs use it directly.
//! * The `milkwashr` Python extension module gives the same functions to
//!   Python. Build it with the `python` feature, which is on by default.
//! * The `milkwashr-wasm` crate gives the same functions to a browser.

pub mod chunking;

pub use chunking::{
    assemble_chunks, plan_chunk_spans, prompt_index, split_by_size, text_seed, XorShift64, PROMPTS,
};

#[cfg(feature = "python")]
mod python;
