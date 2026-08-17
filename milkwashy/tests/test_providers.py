# this_file: milkwashy/tests/test_providers.py
"""Model ordering: `--limit N` must mean the same N models on every run."""

from __future__ import annotations

import httpx
import pytest
from milkwashy.config import Provider

from milkwashy import providers

PROV = Provider(name="fake", endpoint="http://127.0.0.1:9/v1", lister="openai")


def _payload(ids):
    return {"data": [{"id": i} for i in ids]}


@pytest.fixture
def api(monkeypatch):
    """Stub /v1/models, and treat the endpoint as reachable."""
    box: dict = {}

    def get(url, **kwargs):
        return httpx.Response(200, json=box["payload"], request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(providers, "resolve_endpoint", lambda _p: PROV.endpoint)
    return box


def test_openai_models_sorted_regardless_of_api_order(api):
    api["payload"] = _payload(["grok-4.6", "GPT-5", "aardvark", "zzz"])
    first = [m.key for m in providers.list_openai_models(PROV)]

    api["payload"] = _payload(["zzz", "aardvark", "grok-4.6", "GPT-5"])
    second = [m.key for m in providers.list_openai_models(PROV)]

    assert first == second, "a reshuffled API response must give the same order"
    assert first == sorted(first)


def test_limit_selects_the_same_models_across_runs(api):
    """The failure this prevents: --limit 1 hitting a different model each run."""
    api["payload"] = _payload(["m-c", "m-a", "m-b"])
    assert [m.key for m in providers.list_openai_models(PROV)][:1] == ["m-a"]

    api["payload"] = _payload(["m-b", "m-c", "m-a"])
    assert [m.key for m in providers.list_openai_models(PROV)][:1] == ["m-a"]


def test_size_still_dominates_the_ordering():
    models = [
        providers.ModelInfo(key="big", size_bytes=100),
        providers.ModelInfo(key="a-small", size_bytes=1),
        providers.ModelInfo(key="b-small", size_bytes=1),
    ]
    models.sort(key=providers._order)
    assert [m.key for m in models] == ["a-small", "b-small", "big"]
