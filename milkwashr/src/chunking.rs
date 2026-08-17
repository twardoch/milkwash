//! this_file: milkwashr/src/chunking.rs
//!
//! Chunk assembly, with no Python and no operating system calls.
//!
//! This module holds all of the logic. The Python bindings in `python.rs` and
//! the WebAssembly bindings in the `milkwashr-wasm` crate are only thin covers
//! over these functions. Because of this, all three targets give the same
//! result for the same input.

use blake2::digest::{Update, VariableOutput};
use blake2::Blake2bVar;
use text_splitter::{ChunkConfig, TextSplitter};

/// The four rephrase prompts, in the order that gives their index.
///
/// `milkwashy` shows the same list. Do not change the order. The index goes
/// into each output manifest, and a different order makes old and new runs
/// impossible to compare.
pub const PROMPTS: [&str; 4] = [
    "Shorten the text by 10%, preserve the tone but use some synonyms",
    "Expand the text by 10%, preserve the tone but use some synonyms",
    "Preserve the text but use some synonyms",
    "Rephrase this text to be more ASD-STE100",
];

/// A small deterministic random number generator (xorshift64*).
///
/// Each source text gets its own seed. Because of this, all of the models in a
/// sweep get the same chunks.
pub struct XorShift64 {
    state: u64,
}

impl XorShift64 {
    pub fn new(seed: u64) -> Self {
        // A state of zero gives only zeros, so replace it.
        XorShift64 {
            state: if seed == 0 {
                0x9E37_79B9_7F4A_7C15
            } else {
                seed
            },
        }
    }

    pub fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// Gives an integer from `lo` to `hi`. Both limits are included.
    pub fn range_inclusive(&mut self, lo: usize, hi: usize) -> usize {
        if hi <= lo {
            return lo;
        }
        let span = (hi - lo + 1) as u64;
        lo + (self.next_u64() % span) as usize
    }
}

/// Calculates the 64-bit seed for a text.
///
/// The seed is the first 8 bytes of the BLAKE2b hash of the UTF-8 text, read as
/// a big-endian integer. `milkwashy.segment.text_seed` calculates the same
/// value in Python. The test `seed_matches_python_reference` holds that
/// agreement in place.
pub fn text_seed(text: &str) -> u64 {
    let mut hasher = Blake2bVar::new(8).expect("8 bytes is a permitted BLAKE2b output size");
    hasher.update(text.as_bytes());
    let mut digest = [0u8; 8];
    hasher
        .finalize_variable(&mut digest)
        .expect("the buffer has the size that was requested");
    u64::from_be_bytes(digest)
}

/// Gives the prompt index for chunk `index` of a text with seed `seed`.
///
/// This is the Rust equivalent of the Python prompt selection. Both use the
/// same seed, so both give the same prompt for the same chunk.
pub fn prompt_index(seed: u64, index: usize) -> usize {
    let mut rng = XorShift64::new(seed);
    let mut choice = 0;
    for _ in 0..=index {
        choice = (rng.next_u64() % PROMPTS.len() as u64) as usize;
    }
    choice
}

/// Groups sentence positions into chunks of `min_sent` to `max_sent` sentences.
///
/// The result is a list of half-open ranges over the sentence list. The ranges
/// touch, and together they cover all of the sentences.
pub fn plan_chunk_spans(
    n_sentences: usize,
    seed: u64,
    min_sent: usize,
    max_sent: usize,
) -> Vec<(usize, usize)> {
    let low = min_sent.max(1);
    let high = max_sent.max(low);
    let mut rng = XorShift64::new(seed);
    let mut spans = Vec::new();
    let mut start = 0usize;
    while start < n_sentences {
        let want = rng.range_inclusive(low, high);
        let end = (start + want).min(n_sentences);
        spans.push((start, end));
        start = end;
    }
    spans
}

/// Builds chunk texts from sentences that are already separated.
///
/// The function groups the sentences, joins each group with one space, and then
/// applies `text-splitter` as a size guard. If a group is longer than
/// `max_chars` characters, the guard cuts it into smaller parts. The order of
/// the text does not change.
pub fn assemble_chunks(
    sentences: &[String],
    seed: u64,
    min_sent: usize,
    max_sent: usize,
    max_chars: usize,
) -> Vec<String> {
    let spans = plan_chunk_spans(sentences.len(), seed, min_sent, max_sent);
    let guard = max_chars.max(1);
    let splitter = TextSplitter::new(ChunkConfig::new(guard));
    let mut chunks = Vec::with_capacity(spans.len());
    for (start, end) in spans {
        let joined = sentences[start..end].join(" ");
        if joined.chars().count() <= guard {
            chunks.push(joined);
        } else {
            chunks.extend(splitter.chunks(&joined).map(str::to_string));
        }
    }
    chunks
}

/// Cuts a text by size only. Use this when the sentences are not available.
pub fn split_by_size(text: &str, max_chars: usize) -> Vec<String> {
    let splitter = TextSplitter::new(ChunkConfig::new(max_chars.max(1)));
    splitter.chunks(text).map(str::to_string).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sentences(count: usize) -> Vec<String> {
        (0..count)
            .map(|i| format!("Sentence number {i}."))
            .collect()
    }

    #[test]
    fn seed_matches_python_reference() {
        // Reference values from CPython:
        //   int.from_bytes(hashlib.blake2b(text.encode(), digest_size=8).digest(), "big")
        assert_eq!(text_seed(""), 16_476_032_584_258_269_876);
        assert_eq!(text_seed("milkwash"), 6_777_084_162_315_161_999);
        assert_eq!(text_seed("Rzeki i maszyny"), 4_395_667_236_241_783_211);
    }

    #[test]
    fn spans_cover_every_sentence_exactly_once() {
        let spans = plan_chunk_spans(37, text_seed("cover"), 2, 8);
        assert_eq!(spans.first().unwrap().0, 0);
        assert_eq!(spans.last().unwrap().1, 37);
        for pair in spans.windows(2) {
            assert_eq!(pair[0].1, pair[1].0, "spans must touch and not overlap");
        }
    }

    #[test]
    fn spans_hold_the_requested_sentence_count() {
        let spans = plan_chunk_spans(200, text_seed("limits"), 2, 8);
        // Only the last span can be shorter, because the text ends there.
        for (start, end) in &spans[..spans.len() - 1] {
            let size = end - start;
            assert!((2..=8).contains(&size), "span size {size} is out of range");
        }
    }

    #[test]
    fn the_same_seed_gives_the_same_plan() {
        let seed = text_seed("determinism");
        assert_eq!(
            plan_chunk_spans(50, seed, 2, 8),
            plan_chunk_spans(50, seed, 2, 8)
        );
    }

    #[test]
    fn a_different_seed_gives_a_different_plan() {
        let a = plan_chunk_spans(50, text_seed("text one"), 2, 8);
        let b = plan_chunk_spans(50, text_seed("text two"), 2, 8);
        assert_ne!(a, b);
    }

    #[test]
    fn zero_sentences_give_no_spans() {
        assert!(plan_chunk_spans(0, 1234, 2, 8).is_empty());
    }

    #[test]
    fn a_bad_sentence_range_does_not_stop_the_run() {
        // max_sent below min_sent must not make an empty or endless loop.
        let spans = plan_chunk_spans(9, 1234, 5, 2);
        assert_eq!(spans.last().unwrap().1, 9);
    }

    #[test]
    fn chunks_keep_all_of_the_sentences() {
        let input = sentences(24);
        let chunks = assemble_chunks(&input, text_seed("keep"), 2, 8, 6000);
        let rebuilt = chunks.join(" ");
        for sentence in &input {
            assert!(rebuilt.contains(sentence), "{sentence} is missing");
        }
    }

    #[test]
    fn the_size_guard_cuts_long_chunks() {
        let long = vec!["word ".repeat(400).trim().to_string(); 4];
        let chunks = assemble_chunks(&long, 42, 2, 8, 200);
        assert!(chunks.len() > 1);
        for chunk in &chunks {
            assert!(
                chunk.chars().count() <= 200,
                "chunk is longer than the guard"
            );
        }
    }

    #[test]
    fn split_by_size_respects_the_limit() {
        let text = "Short sentence. ".repeat(80);
        for piece in split_by_size(&text, 120) {
            assert!(piece.chars().count() <= 120);
        }
    }

    #[test]
    fn prompt_index_stays_inside_the_prompt_list() {
        let seed = text_seed("prompts");
        for index in 0..40 {
            assert!(prompt_index(seed, index) < PROMPTS.len());
        }
    }
}
