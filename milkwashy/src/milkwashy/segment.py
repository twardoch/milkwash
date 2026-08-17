# this_file: milkwashy/src/milkwashy/segment.py
"""Sentence segmentation (sentencex) + deterministic chunk/prompt planning.

The chunk plan is computed ONCE per source text from a content-derived seed, so
every model in the sweep is fed the identical chunks with the identical prompt
assignment. Only then are outputs comparable across models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import milkwashr
from sentencex import segment as sx_segment

# The four rephrase prompts. The list lives in Rust, so the Python package, the
# Rust crate and the WebAssembly build cannot disagree. The index goes into each
# output manifest.
PROMPTS: list[str] = list(milkwashr.PROMPTS)


@dataclass
class ChunkPlan:
    index: int
    text: str
    prompt_index: int

    @property
    def prompt(self) -> str:
        return PROMPTS[self.prompt_index]


def text_seed(text: str) -> int:
    """Reproducible 64-bit seed from text content.

    The calculation is the first 8 bytes of the BLAKE2b hash, read as a
    big-endian integer. Rust does the work, so every target gives the same seed.
    """
    return milkwashr.text_seed(text)


def segment_sentences(text: str, language: str) -> list[str]:
    """sentencex sentence boundaries; falls back to whole text if none."""
    sents = [s.strip() for s in sx_segment(language, text) if s.strip()]
    return sents or [text.strip()]


def plan_chunks(
    text: str,
    language: str,
    *,
    min_sent: int = 2,
    max_sent: int = 8,
    max_chars: int = 6000,
) -> list[ChunkPlan]:
    """Segment, assemble 2-8 sentence chunks, and give each chunk one prompt.

    The chunk assembly and the prompt choice both come from the same
    content-derived seed, and both happen in Rust. Because of this, the sweep,
    the Rust crate and the browser demonstration make the same plan.
    """
    seed = text_seed(text)
    sentences = segment_sentences(text, language)
    chunk_texts = milkwashr.assemble_chunks(sentences, seed, min_sent, max_sent, max_chars)
    return [
        ChunkPlan(index=i, text=ct, prompt_index=milkwashr.prompt_index(seed, i))
        for i, ct in enumerate(chunk_texts)
    ]


def plan_to_dicts(plans: list[ChunkPlan]) -> list[dict]:
    return [asdict(p) | {"prompt": p.prompt} for p in plans]
