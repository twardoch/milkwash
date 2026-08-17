# this_file: milkwashy/src/milkwashy/segment.py
"""Sentence segmentation (sentencex) + deterministic chunk/prompt planning.

The chunk plan is computed ONCE per source text from a content-derived seed, so
every model in the sweep is fed the identical chunks with the identical prompt
assignment. Only then are outputs comparable across models.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass

import milkwashr
from sentencex import segment as sx_segment

# The four rephrase prompts (from the issue). Index is stored in the manifest.
PROMPTS = [
    "Shorten the text by 10%, preserve the tone but use some synonyms",
    "Expand the text by 10%, preserve the tone but use some synonyms",
    "Preserve the text but use some synonyms",
    "Rephrase this text to be more ASD-STE100",
]


@dataclass
class ChunkPlan:
    index: int
    text: str
    prompt_index: int

    @property
    def prompt(self) -> str:
        return PROMPTS[self.prompt_index]


def text_seed(text: str) -> int:
    """Reproducible 64-bit seed from text content."""
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


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
    """Segment, assemble 2-8 sentence chunks (Rust), assign a random prompt each.

    Both the chunk assembly (in milkwashr) and the prompt choice are driven by
    the same content-derived seed, making the whole plan reproducible.
    """
    seed = text_seed(text)
    sentences = segment_sentences(text, language)
    chunk_texts = milkwashr.assemble_chunks(sentences, seed, min_sent, max_sent, max_chars)
    rng = random.Random(seed)  # independent stream for prompt choice
    return [
        ChunkPlan(index=i, text=ct, prompt_index=rng.randrange(len(PROMPTS)))
        for i, ct in enumerate(chunk_texts)
    ]


def plan_to_dicts(plans: list[ChunkPlan]) -> list[dict]:
    return [asdict(p) | {"prompt": p.prompt} for p in plans]
