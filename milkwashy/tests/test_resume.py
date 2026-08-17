# this_file: milkwashy/tests/test_resume.py
"""Existing outputs are skipped by default; --force rewrites them."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from milkwashy.config import Config, Provider

from milkwashy import pipeline


class FakeChat:
    def __init__(self, owner):
        self.completions = self
        self._owner = owner

    def create(self, *, model, messages, **kwargs):
        self._owner.calls.append((model, messages[-1]["content"][:20]))
        return type(
            "R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "rewritten"})()})()]}
        )()


class FakeClient:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.chat = FakeChat(self)


@pytest.fixture
def sweep(tmp_path, monkeypatch):
    """run_sweep against a fake OpenAI client and one fake model, no lms."""
    client = FakeClient()
    monkeypatch.setattr(pipeline, "make_client", lambda *_a, **_k: client)
    monkeypatch.setattr(
        pipeline, "list_models", lambda *_a, **_k: [pipeline.ModelInfo(key="fake-model", size_bytes=1)]
    )
    cfg = Config()
    provider = Provider(name="fake", endpoint="http://127.0.0.1:9/v1", lister="openai")

    def go(provider_name: str | None = None, **kwargs):
        prov = provider if provider_name is None else replace(provider, name=provider_name)
        return pipeline.run_sweep(
            cfg, prov, project_dir=tmp_path, manage_lms=False, **kwargs
        )

    return go, client, tmp_path


def test_first_run_writes_outputs(sweep):
    go, client, _tmp_path = sweep
    res = go()
    assert res.outputs_written == 4, "one output per input text"
    assert res.outputs_resumed == 0
    assert client.calls, "the model was actually called"


def test_outputs_are_grouped_under_the_provider(sweep):
    """Two providers can serve the same model name; keep their corpora apart."""
    go, _client, tmp_path = sweep
    go()
    model_dir = tmp_path / "02-testllm" / "fake" / "fake-model"
    assert model_dir.is_dir(), "outputs belong under 02-testllm/<provider>/<model>/"
    assert len(list(model_dir.glob("*.txt"))) == 4
    assert not (tmp_path / "02-testllm" / "fake-model").exists(), "no flat model dir"


def test_provider_folder_is_lowercased(sweep):
    go, _client, tmp_path = sweep
    go(provider_name="LMStudio")
    assert (tmp_path / "02-testllm" / "lmstudio" / "fake-model").is_dir()


def test_second_run_skips_existing_outputs(sweep):
    go, client, _tmp_path = sweep
    go()
    client.calls.clear()
    res = go()
    assert res.outputs_written == 0
    assert res.outputs_resumed == 4
    assert client.calls == [], "no inference for outputs that already exist"


def test_force_rewrites_existing_outputs(sweep):
    go, client, tmp_path = sweep
    go()
    out = next((tmp_path / "02-testllm" / "fake" / "fake-model").glob("*.txt"))
    out.write_text("stale", encoding="utf-8")
    client.calls.clear()

    res = go(force=True)
    assert res.outputs_written == 4
    assert client.calls, "--force must re-run inference"
    assert out.read_text(encoding="utf-8") != "stale"


def test_partial_outputs_only_fill_the_gaps(sweep):
    go, client, tmp_path = sweep
    go()
    model_dir = tmp_path / "02-testllm" / "fake" / "fake-model"
    next(model_dir.glob("*.txt")).unlink()
    client.calls.clear()

    res = go()
    assert (res.outputs_written, res.outputs_resumed) == (1, 3)


def _write_skip(tmp_path, reason: str):
    model_dir = tmp_path / "02-testllm" / "fake" / "fake-model"
    model_dir.mkdir(parents=True)
    (model_dir / "_skipped.json").write_text(
        json.dumps({"model": "fake-model", "reason": reason}), encoding="utf-8"
    )


def test_model_that_could_not_load_is_not_retried(sweep):
    """`load_failed` is a property of the model; retrying costs a load each sweep."""
    go, client, tmp_path = sweep
    _write_skip(tmp_path, "load_failed")
    res = go()
    assert res.models_skipped == 1
    assert client.calls == [], "an unloadable model must not cost another load/probe"


def test_probe_failure_is_retried(sweep):
    """A server on the wrong port marks EVERY model probe_failed.

    Honouring that marker would make the corrected re-run skip the whole
    catalogue and report success having produced nothing.
    """
    go, client, tmp_path = sweep
    _write_skip(tmp_path, "probe_failed")
    res = go()
    assert res.outputs_written == 4, "a transient failure must not be permanent"
    assert client.calls, "the model was re-probed"


def test_force_retries_even_an_unloadable_model(sweep):
    go, client, tmp_path = sweep
    _write_skip(tmp_path, "load_failed")
    res = go(force=True)
    assert res.outputs_written == 4
    assert client.calls
