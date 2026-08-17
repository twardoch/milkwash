# this_file: milkwashy/tests/test_rust_agreement.py
"""The Python plan must be the Rust plan.

`milkwashr` holds the seed calculation, the chunk assembly, the prompt list and
the prompt choice. Python must not make its own version of any of them. If it
does, a sweep, a Rust program and the browser demonstration give different
chunks, and no result can be compared.
"""

from __future__ import annotations

import hashlib

import milkwashr
import pytest

from milkwashy.segment import PROMPTS, plan_chunks, segment_sentences, text_seed

TEXT = (
    "Rivers move slowly here. The old machines still turn. "
    "Nobody remembers the first winter. The wheel stopped once. "
    "The miller repaired it in one day. People came to watch. "
    "Water is patient. Steel is not. The village kept both."
)


def test_prompts_come_from_rust():
    assert PROMPTS == list(milkwashr.PROMPTS)
    assert len(PROMPTS) == 4
    assert PROMPTS[3] == "Rephrase this text to be more ASD-STE100"


def test_text_seed_matches_blake2b():
    # The definition is the first 8 bytes of BLAKE2b as a big-endian integer.
    expected = int.from_bytes(hashlib.blake2b(TEXT.encode(), digest_size=8).digest(), "big")
    assert text_seed(TEXT) == expected
    assert milkwashr.text_seed(TEXT) == expected


def test_text_seed_is_stable_for_known_inputs():
    assert milkwashr.text_seed("") == 16476032584258269876
    assert milkwashr.text_seed("milkwash") == 6777084162315161999


def test_prompt_choice_comes_from_rust():
    seed = text_seed(TEXT)
    plans = plan_chunks(TEXT, "en")
    assert plans, "the example text must give at least one chunk"
    for plan in plans:
        assert plan.prompt_index == milkwashr.prompt_index(seed, plan.index)
        assert plan.prompt == PROMPTS[plan.prompt_index]


def test_prompt_index_stays_inside_the_list():
    seed = text_seed(TEXT)
    for index in range(64):
        assert 0 <= milkwashr.prompt_index(seed, index) < len(PROMPTS)


def test_chunk_text_comes_from_rust():
    seed = text_seed(TEXT)
    sentences = segment_sentences(TEXT, "en")
    expected = milkwashr.assemble_chunks(sentences, seed, 2, 8, 6000)
    assert [plan.text for plan in plan_chunks(TEXT, "en")] == expected


def test_the_same_text_gives_the_same_plan():
    first = [(p.text, p.prompt_index) for p in plan_chunks(TEXT, "en")]
    second = [(p.text, p.prompt_index) for p in plan_chunks(TEXT, "en")]
    assert first == second


def test_a_different_text_gives_a_different_seed():
    assert text_seed(TEXT) != text_seed(TEXT + " One more sentence.")


@pytest.mark.parametrize("max_chars", [80, 200])
def test_the_size_guard_holds(max_chars):
    plans = plan_chunks(TEXT, "en", max_chars=max_chars)
    for plan in plans:
        assert len(plan.text) <= max_chars


def test_no_text_disappears():
    plans = plan_chunks(TEXT, "en", max_chars=100)
    squeeze = lambda value: "".join(value.split())  # noqa: E731
    assert squeeze("".join(p.text for p in plans)) == squeeze(TEXT)
