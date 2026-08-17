# this_file: milkwashy/tests/test_custom_provider.py
"""A server that only exists in the TOML file must behave like a built-in one."""

from __future__ import annotations

from milkwashy.config import load_config

TOML = """
default_provider = "myserver"

[providers.myserver]
lister = "openai"
"""


def write_config(tmp_path, body: str):
    target = tmp_path / "config.toml"
    target.write_text(body, encoding="utf-8")
    return target


def test_custom_provider_reads_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("MYSERVER_API_ENDPOINT", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("MYSERVER_API_KEY", "sk-test-1234")
    config = load_config(write_config(tmp_path, TOML))
    provider = config.providers["myserver"]
    assert provider.endpoint == "http://127.0.0.1:9000/v1"
    assert provider.api_key == "sk-test-1234"
    assert provider.lister == "openai"


def test_the_toml_file_wins_over_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("MYSERVER_API_ENDPOINT", "http://from-env:9000/v1")
    body = TOML + '\nendpoint = "http://from-toml:9000/v1"\n'
    config = load_config(write_config(tmp_path, body))
    assert config.providers["myserver"].endpoint == "http://from-toml:9000/v1"


def test_a_missing_key_gets_the_placeholder(tmp_path, monkeypatch):
    monkeypatch.delenv("MYSERVER_API_KEY", raising=False)
    config = load_config(write_config(tmp_path, TOML))
    # LM Studio and similar servers ignore the key, so a placeholder is correct.
    assert config.providers["myserver"].api_key == "not-needed"


def test_the_built_in_providers_stay_available(tmp_path):
    config = load_config(write_config(tmp_path, TOML))
    assert {"lmstudio", "chat2api", "cliproxy"} <= set(config.providers)
    assert config.default_provider == "myserver"


def test_cliproxy_keeps_its_port_fallback(tmp_path):
    config = load_config(write_config(tmp_path, TOML))
    assert config.providers["cliproxy"].port_fallback_subtract == 10000
    assert config.providers["lmstudio"].port_fallback_subtract == 0
