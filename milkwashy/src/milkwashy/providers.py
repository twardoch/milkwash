# this_file: milkwashy/src/milkwashy/providers.py
"""Provider model-list readers and endpoint reachability.

Each OpenAI-compatible provider returns its model list in a different shape, so
listing is per-provider:
  - lmstudio: the `lms` CLI (authoritative for LM Studio, incl. sizeBytes)
  - openai:   GET {endpoint}/models
"""

from __future__ import annotations

import json
import socket
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx
from loguru import logger

from .config import Provider


@dataclass
class ModelInfo:
    key: str            # id passed to the OpenAI API `model` field
    size_bytes: int = 0
    arch: str | None = None


def _order(m: ModelInfo) -> tuple[int, str]:
    """Sort key: size ascending, then model key.

    The tiebreak is what makes `--limit N` mean the same N models on every run.
    OpenAI-compatible `/v1/models` reports no size (all zero) and does not
    promise a stable order, so without it a bounded sweep would scatter partial
    output across a different subset each time.
    """
    return (m.size_bytes, m.key)


def _parse_lms_json(raw: bytes | str) -> list[dict]:
    """Robustly extract the JSON array from `lms ls --json` output.

    `script -q /dev/null lms ...` prepends control bytes (^D etc.); jq chokes.
    Slice from the first '[' to the last ']' and json.loads that.
    """
    s = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else raw
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1:
        return []
    return json.loads(s[start : end + 1])


def list_lms_models() -> list[ModelInfo]:
    """LM Studio models via the `lms` CLI, sorted by sizeBytes ascending."""
    try:
        proc = subprocess.run(
            ["script", "-q", "/dev/null", "lms", "ls", "--json", "--llm"],
            capture_output=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"lms CLI unavailable: {exc}")
        return []
    data = _parse_lms_json(proc.stdout)
    models = [
        ModelInfo(
            key=m.get("modelKey") or m.get("path", ""),
            size_bytes=int(m.get("sizeBytes", 0)),
            arch=m.get("architecture"),
        )
        for m in data
        if m.get("type") == "llm" and (m.get("modelKey") or m.get("path"))
    ]
    models.sort(key=_order)
    return models


def list_openai_models(provider: Provider) -> list[ModelInfo]:
    """Models via GET {endpoint}/models (OpenAI /v1/models shape)."""
    base = resolve_endpoint(provider)
    if base is None:
        return []
    url = base.rstrip("/") + "/models"
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {provider.api_key}"}, timeout=15)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:  # noqa: BLE001 - provider optional; degrade gracefully
        logger.warning(f"{provider.name}: cannot list models at {url}: {exc}")
        return []
    rows = payload.get("data", payload if isinstance(payload, list) else [])
    models = [ModelInfo(key=row["id"]) for row in rows if isinstance(row, dict) and "id" in row]
    models.sort(key=_order)
    return models


def list_models(provider: Provider) -> list[ModelInfo]:
    if provider.lister == "lms":
        return list_lms_models()
    return list_openai_models(provider)


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_endpoint(provider: Provider) -> str | None:
    """Return a reachable base URL, applying the CLIPROXY port-fallback rule.

    If the configured port isn't reachable and `port_fallback_subtract` is set
    (CLIPROXY: 10000), retry with (port - subtract).
    """
    parsed = urlparse(provider.endpoint)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if port is None:
        return provider.endpoint  # scheme default port; assume caller-managed

    if _port_open(host, port):
        return provider.endpoint

    if provider.port_fallback_subtract:
        alt_port = port - provider.port_fallback_subtract
        if alt_port > 0 and _port_open(host, alt_port):
            netloc = f"{parsed.hostname}:{alt_port}"
            logger.info(f"{provider.name}: port {port} closed, using fallback {alt_port}")
            return urlunparse(parsed._replace(netloc=netloc))

    logger.warning(f"{provider.name}: endpoint {provider.endpoint} unreachable")
    return None
