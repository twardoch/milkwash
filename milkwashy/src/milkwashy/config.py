# this_file: milkwashy/src/milkwashy/config.py
"""TOML configuration in a platformdirs-determined location, plus provider env.

Config precedence for provider endpoint/key:
  1. explicit value in the TOML config file
  2. environment variable (loaded from .env by python-dotenv)
  3. built-in default
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w
from dotenv import load_dotenv
from platformdirs import user_config_path

APP_NAME = "milkwashy"

# provider key -> (endpoint_env, key_env, default_endpoint)
PROVIDER_ENV = {
    "lmstudio": ("LMSTUDIO_API_ENDPOINT", "LMSTUDIO_API_KEY", "http://127.0.0.1:1234/v1"),
    "chat2api": ("CHAT2API_API_ENDPOINT", "CHAT2API_API_KEY", "http://127.0.0.1:8318/v1"),
    "cliproxy": ("CLIPROXY_API_ENDPOINT", "CLIPROXY_API_KEY", "http://0.0.0.0:18317/v1"),
}


@dataclass
class Provider:
    name: str
    endpoint: str
    api_key: str = "not-needed"
    # how to list models: "lms" (use the lms CLI) or "openai" (GET /v1/models)
    lister: str = "openai"
    # cliproxy: try endpoint port, else subtract this from the port
    port_fallback_subtract: int = 0


@dataclass
class Config:
    default_provider: str = "lmstudio"
    indata_dir: str = "01-indata"
    outdata_dir: str = "02-testllm"
    min_sentences: int = 2
    max_sentences: int = 8
    max_chars: int = 6000
    max_tokens: int = 2048
    temperature: float = 0.8
    request_timeout: float = 120.0
    providers: dict[str, Provider] = field(default_factory=dict)


def config_path() -> Path:
    return user_config_path(APP_NAME, ensure_exists=True) / "config.toml"


def _provider_from_env(name: str, raw: dict | None) -> Provider:
    raw = raw or {}
    endpoint_env, key_env, default_ep = PROVIDER_ENV.get(name, (None, None, ""))
    endpoint = raw.get("endpoint") or (os.getenv(endpoint_env) if endpoint_env else None) or default_ep
    api_key = raw.get("api_key") or (os.getenv(key_env) if key_env else None) or "not-needed"
    lister = raw.get("lister", "lms" if name == "lmstudio" else "openai")
    sub = raw.get("port_fallback_subtract", 10000 if name == "cliproxy" else 0)
    return Provider(name=name, endpoint=endpoint, api_key=api_key, lister=lister, port_fallback_subtract=sub)


def load_config(path: Path | None = None) -> Config:
    """Load .env then the TOML config, materialising every known provider."""
    load_dotenv()  # populate os.environ from ./.env if present
    path = path or config_path()
    raw: dict = {}
    if path.exists():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))

    cfg = Config()
    for f in ("default_provider", "indata_dir", "outdata_dir", "min_sentences",
              "max_sentences", "max_chars", "max_tokens", "temperature", "request_timeout"):
        if f in raw:
            setattr(cfg, f, raw[f])

    raw_providers = raw.get("providers", {})
    for name in PROVIDER_ENV:
        cfg.providers[name] = _provider_from_env(name, raw_providers.get(name))
    # allow extra providers defined only in TOML
    for name, praw in raw_providers.items():
        if name not in cfg.providers:
            cfg.providers[name] = Provider(
                name=name,
                endpoint=praw.get("endpoint", ""),
                api_key=praw.get("api_key", "not-needed"),
                lister=praw.get("lister", "openai"),
            )
    return cfg


def write_default_config(path: Path | None = None, force: bool = False) -> Path:
    """Write a documented default config.toml if none exists."""
    path = path or config_path()
    if path.exists() and not force:
        return path
    doc = {
        "default_provider": "lmstudio",
        "indata_dir": "01-indata",
        "outdata_dir": "02-testllm",
        "min_sentences": 2,
        "max_sentences": 8,
        "max_chars": 6000,
        "max_tokens": 2048,
        "temperature": 0.8,
        "request_timeout": 120.0,
        "providers": {
            name: {
                "endpoint": PROVIDER_ENV[name][2],
                "api_key": "",  # empty -> read from env / .env
                "lister": "lms" if name == "lmstudio" else "openai",
                **({"port_fallback_subtract": 10000} if name == "cliproxy" else {}),
            }
            for name in PROVIDER_ENV
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(doc), encoding="utf-8")
    return path


if sys.version_info < (3, 11):  # pragma: no cover
    raise RuntimeError("milkwashy needs Python >= 3.11 (tomllib)")
