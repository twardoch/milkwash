#!/usr/bin/env python3
# this_file: scripts/wasm-reference.py
"""Writes the reference plan that the WebAssembly parity test compares against.

The values come from the Python extension module and from `sentencex`, which is
what a real sweep uses. The parity test then gives the same sentences to the
WebAssembly build. Both must agree.

    wasm-reference.py OUTPUT.json VERSION
"""

from __future__ import annotations

import json
import sys

import milkwashr
from milkwashy.indata import TEXTS
from milkwashy.segment import plan_chunks, segment_sentences, text_seed

MIN_SENT = 2
MAX_SENT = 8
MAX_CHARS = 6000
# One example uses a small guard, so the parity test also covers the size guard.
GUARD_EXAMPLE_CHARS = 220


def example(name: str, text: str, language: str, max_chars: int) -> dict:
    sentences = segment_sentences(text, language)
    joined = " ".join(sentences)
    seed = text_seed(joined)
    plans = plan_chunks(
        joined,
        language,
        min_sent=MIN_SENT,
        max_sent=MAX_SENT,
        max_chars=max_chars,
    )
    return {
        "name": name,
        "language": language,
        "sentences": sentences,
        "joined": joined,
        "seed": str(seed),
        "min_sent": MIN_SENT,
        "max_sent": MAX_SENT,
        "max_chars": max_chars,
        "spans": [
            list(span)
            for span in milkwashr.plan_chunk_spans(len(sentences), seed, MIN_SENT, MAX_SENT)
        ],
        "chunks": [
            {"text": plan.text, "prompt_index": plan.prompt_index} for plan in plans
        ],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    destination, version = argv

    examples = [
        example(f"{code}:{stem}", text, code, MAX_CHARS)
        for code, (stem, text) in TEXTS.items()
    ]
    # The same English text again, with a small guard, to exercise the cut.
    english_stem, english_text = TEXTS["en"]
    examples.append(
        example(f"en:{english_stem}:guard", english_text, "en", GUARD_EXAMPLE_CHARS)
    )

    payload = {
        "version": version,
        "prompts": list(milkwashr.PROMPTS),
        "examples": examples,
    }
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    print(f"reference written: {destination} ({len(examples)} examples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
