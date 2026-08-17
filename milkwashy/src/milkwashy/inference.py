# this_file: milkwashy/src/milkwashy/inference.py
"""OpenAI-compatible inference client with simple bounded retry."""

from __future__ import annotations

import time

from loguru import logger
from openai import OpenAI

from .config import Config, Provider
from .providers import resolve_endpoint


def make_client(provider: Provider, cfg: Config) -> OpenAI | None:
    base = resolve_endpoint(provider)
    if base is None:
        return None
    return OpenAI(base_url=base, api_key=provider.api_key or "not-needed", timeout=cfg.request_timeout)


def rephrase(client: OpenAI, model: str, prompt: str, chunk: str, cfg: Config,
             retries: int = 2) -> str:
    """Run one rephrase prompt against one chunk; return model text.

    Raises the last exception after `retries` attempts so the caller can record
    a skip for this (model, text) and continue.
    """
    messages = [
        {"role": "system", "content": "You are a careful text editor. Output only the rewritten text, no preamble."},
        {"role": "user", "content": f"{prompt}.\n\nText:\n{chunk}"},
    ]
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = 1.5 * (attempt + 1)
            logger.debug(f"{model}: attempt {attempt + 1} failed ({exc}); retry in {wait:.1f}s")
            time.sleep(wait)
    assert last is not None
    raise last
