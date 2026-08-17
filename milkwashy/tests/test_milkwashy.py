# this_file: milkwashy/tests/test_milkwashy.py
"""Core tests: naming, determinism, segmentation, config."""

from __future__ import annotations

import milkwashr
import pytest

from milkwashy.config import Config, load_config
from milkwashy.naming import filenamify
from milkwashy.segment import PROMPTS, plan_chunks, segment_sentences, text_seed


# --- naming -----------------------------------------------------------------

def test_filenamify_when_plain_slug_then_no_hash_tag():
    assert filenamify("simple-name") == "simple-name"


def test_filenamify_when_slug_differs_then_appends_hash():
    out = filenamify("qikp/supra-50m-reasoning")
    assert out.startswith("qikp-supra-50m-reasoning-"), out
    assert len(out.rsplit("-", 1)[1]) == 6, "blake2b digest_size=3 -> 6 hex chars"


def test_filenamify_when_reserved_name_then_prefixed():
    assert filenamify("con").startswith("file-"), "Windows reserved name must be escaped"


def test_filenamify_when_non_latin_then_falls_back_to_hash():
    out = filenamify("模型")
    assert out, "must never return an empty filename"


def test_filenamify_when_extension_given_then_appended():
    assert filenamify("my model", ext="txt").endswith(".txt")


def test_filenamify_when_very_long_then_within_byte_budget():
    assert len(filenamify("x" * 500).encode()) <= 255


# --- determinism (the load-bearing property) --------------------------------

def test_text_seed_when_same_text_then_same_seed():
    assert text_seed("hello world") == text_seed("hello world")
    assert text_seed("hello world") != text_seed("hello worlds")


def test_plan_chunk_spans_when_same_seed_then_identical():
    a = milkwashr.plan_chunk_spans(30, 999, 2, 8)
    b = milkwashr.plan_chunk_spans(30, 999, 2, 8)
    assert a == b


def test_plan_chunk_spans_when_different_seed_then_differs():
    a = milkwashr.plan_chunk_spans(50, 1, 2, 8)
    b = milkwashr.plan_chunk_spans(50, 2, 2, 8)
    assert a != b, "different seeds should give different chunkings"


def test_plan_chunk_spans_covers_all_sentences_without_gaps():
    spans = milkwashr.plan_chunk_spans(37, 4242, 2, 8)
    assert spans[0][0] == 0
    assert spans[-1][1] == 37
    for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
        assert prev_end == next_start, "spans must tile the sentence list"


def test_plan_chunk_spans_respects_bounds_except_final_remainder():
    spans = milkwashr.plan_chunk_spans(100, 7, 2, 8)
    for start, end in spans[:-1]:
        assert 2 <= end - start <= 8


def test_plan_chunks_when_same_text_then_same_prompts():
    text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten."
    a = plan_chunks(text, "en")
    b = plan_chunks(text, "en")
    assert [(c.text, c.prompt_index) for c in a] == [(c.text, c.prompt_index) for c in b]


def test_plan_chunks_prompt_index_in_range():
    text = " ".join(f"Sentence {i}." for i in range(40))
    for cp in plan_chunks(text, "en"):
        assert 0 <= cp.prompt_index < len(PROMPTS)
        assert cp.prompt in PROMPTS


# --- edge cases -------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "   ", "Single sentence."])
def test_plan_chunks_when_degenerate_input_then_no_crash(text):
    plan_chunks(text, "en")  # must not raise


def test_assemble_chunks_when_oversized_then_size_guarded():
    huge = ["word " * 3000, "short one."]
    chunks = milkwashr.assemble_chunks(huge, 1, 2, 8, 500)
    assert all(len(c) <= 600 for c in chunks), "size guard must cap chunk length"


# --- segmentation -----------------------------------------------------------

def test_segment_sentences_english():
    assert len(segment_sentences("First one. Second one! Third one?", "en")) == 3


def test_segment_sentences_arabic():
    assert len(segment_sentences("كانت الطاحونة قديمة. طحنت القمح.", "ar")) == 2


def test_segment_sentences_polish():
    assert len(segment_sentences("Stary młyn stał w zakolu. Woda zwalniała.", "pl")) == 2


# --- config -----------------------------------------------------------------

def test_load_config_registers_all_three_providers():
    cfg = load_config()
    assert {"lmstudio", "chat2api", "cliproxy"} <= set(cfg.providers)


def test_lmstudio_uses_lms_lister_not_openai():
    assert load_config().providers["lmstudio"].lister == "lms"


def test_cliproxy_has_port_fallback_rule():
    assert load_config().providers["cliproxy"].port_fallback_subtract == 10000


def test_config_defaults_match_issue_spec():
    cfg = Config()
    assert (cfg.min_sentences, cfg.max_sentences) == (2, 8)
