# this_file: milkwashy/src/milkwashy/lmsctl.py
"""LM Studio (`lms` CLI) control: server lifecycle and model residency.

The load/unload invariant this module enforces:

    NO model may be loaded while another model is resident.

It is enforced at the *load* site (`load_exclusive`), not by remembering to
unload at the bottom of a caller's loop -- every ``continue``, ``break`` and
exception path in a caller is otherwise a hole. Residency is verified against
``lms ps --json`` rather than trusted from an exit code, because a failed
``lms unload`` returns non-zero and would otherwise be silently discarded.

If residency cannot be proven empty, `LmsResidencyError` is raised and the
caller must abort: continuing would load a second model on top of the first.
"""

from __future__ import annotations

import json
import re
import subprocess
import time

import httpx
from loguru import logger

LMS_TIMEOUT = 300
SERVER_RUNNING_MARKER = "The server is running on port"
SERVER_STOPPED_MARKER = "The server is not running"


class LmsError(RuntimeError):
    """The `lms` CLI is unusable (absent, timing out, or server unstartable)."""


class LmsResidencyError(LmsError):
    """Models are still resident after every unload attempt."""


def _run(
    args: list[str], timeout: int = LMS_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """Invoke `lms` with stdin closed.

    `lms unload` prompts interactively when it cannot resolve a single target;
    with captured output and an inherited stdin that prompt would block for the
    full timeout. DEVNULL makes it fail fast instead.
    """
    try:
        return subprocess.run(
            ["lms", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            check=False,  # every caller inspects returncode itself
        )
    except FileNotFoundError as exc:
        raise LmsError("`lms` CLI not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise LmsError(f"`lms {' '.join(args)}` timed out after {timeout}s") from exc


# --- server -----------------------------------------------------------------


def server_port() -> int | None:
    """Port the LM Studio server reports itself running on, or None if down.

    `lms server status` writes to stderr, so both streams are matched.
    """
    out = _run(["server", "status"], timeout=30)
    text = (out.stdout or "") + (out.stderr or "")
    match = re.search(rf"{SERVER_RUNNING_MARKER} (\d+)", text)
    if match:
        return int(match.group(1))
    if SERVER_STOPPED_MARKER not in text:
        logger.debug(f"lms server status unrecognised: {text.strip()[:200]!r}")
    return None


def server_status() -> bool:
    """True if the LM Studio server is running (issue step 4)."""
    return server_port() is not None


def _api_answers(base_url: str, timeout: float = 8.0) -> bool:
    """True if {base_url}/models answers over HTTP.

    A TCP connect is not enough: a wedged LM Studio socket accepts connections
    and then never replies, which looks alive to a port check and fails every
    model with `probe_failed` hours later.
    """
    try:
        r = httpx.get(base_url.rstrip("/") + "/models", timeout=timeout)
        return r.status_code < 500
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"{base_url}/models did not answer: {exc}")
        return False


def ensure_server(port: int | None = None, base_url: str | None = None) -> None:
    """Ensure the LM Studio server is up *on the port the client will use*.

    `lms server start` with no `--port` reuses the last-used port, so starting
    it blind can bring the server up on 1235 while inference is configured for
    1234 -- `server_status()` would say "running" and every model would then fail
    to probe. The port is therefore always passed explicitly and cross-checked,
    and `base_url` (when given) is confirmed to actually answer HTTP.
    """
    running_on = server_port()

    if running_on is not None and port is not None and running_on != port:
        raise LmsError(
            f"lms server is running on port {running_on}, but inference is configured "
            f"for port {port}. Point the config/endpoint at {running_on}, or restart "
            f"the server with `lms server start --port {port}`."
        )

    if running_on is None:
        logger.info(f"lms server not running; starting{f' on port {port}' if port else ''}")
        out = _run(["server", "start", *(["--port", str(port)] if port else [])], timeout=120)
        running_on = server_port()
        if running_on is None:
            detail = ((out.stdout or "") + (out.stderr or "")).strip()[:200]
            if "EADDRINUSE" in detail:
                # Another process holds the port while lms considers the server
                # down -- typically a wedged LM Studio app socket, which accepts
                # TCP but never answers HTTP. Restarting the app frees it.
                raise LmsError(
                    f"lms server is down but its port is held by another process ({detail}). "
                    "Restart LM Studio (or toggle its server off and on) to free the port."
                )
            raise LmsError(f"could not start lms server: {detail}")
        logger.info(f"lms server started on port {running_on}")
    else:
        logger.debug(f"lms server already running on port {running_on}")

    if base_url and not _api_answers(base_url):
        raise LmsError(
            f"lms reports the server running on port {running_on}, but {base_url}/models "
            "does not answer. Restart LM Studio to clear the stale socket."
        )


# --- residency --------------------------------------------------------------


def loaded() -> list[str]:
    """Identifiers of currently loaded models, per `lms ps --json`.

    Loaded *instance* identifiers are reported in the `identifier` field, which
    may differ from `modelKey` (a second instance of one model gets a suffixed
    identifier), so unloading is driven by this field rather than by the key the
    caller happens to hold.
    """
    out = _run(["ps", "--json"], timeout=60)
    raw = out.stdout or ""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        if out.returncode != 0:
            raise LmsError(
                f"`lms ps --json` failed: {(out.stderr or '').strip()[:200]}"
            )
        return []
    rows = json.loads(raw[start : end + 1])
    return [
        r["identifier"] for r in rows if isinstance(r, dict) and r.get("identifier")
    ]


def unload(identifier: str) -> None:
    """Unload one model; residency is verified separately by the caller."""
    out = _run(["unload", identifier])
    if out.returncode != 0:
        logger.debug(
            f"lms unload {identifier} -> rc={out.returncode}: {(out.stderr or '').strip()[:200]}"
        )


def unload_all() -> None:
    out = _run(["unload", "--all"])
    if out.returncode != 0:
        logger.debug(
            f"lms unload --all -> rc={out.returncode}: {(out.stderr or '').strip()[:200]}"
        )


def ensure_none_loaded(*, settle: float = 0.5) -> None:
    """Guarantee that no model is resident, or raise.

    Targeted unload of everything `ps` reports, then verify; on failure escalate
    to `unload --all` and verify again. A still-non-empty list means residency
    cannot be proven empty, which is a hard stop.
    """
    resident = loaded()
    if not resident:
        return

    logger.info(f"unloading resident models before next load: {resident}")
    for identifier in resident:
        unload(identifier)
    time.sleep(settle)

    resident = loaded()
    if not resident:
        return

    logger.warning(
        f"targeted unload left {resident} resident; escalating to `lms unload --all`"
    )
    unload_all()
    time.sleep(settle)

    resident = loaded()
    if resident:
        raise LmsResidencyError(
            f"models still loaded after targeted unload and `lms unload --all`: {resident}"
        )


def load_exclusive(identifier: str) -> bool:
    """Unload everything, then load `identifier`. Returns False if load failed.

    This is the only supported load path: the residency check runs *inside* it,
    so no caller can load a model while another is resident.
    """
    ensure_none_loaded()
    logger.debug(f"residency verified empty; loading {identifier}")
    out = _run(["load", identifier, "-y"])
    if out.returncode != 0:
        logger.info(f"lms load {identifier} failed: {(out.stderr or '').strip()[:200]}")
        # A partial load can still leave something resident.
        ensure_none_loaded()
        return False
    return True


def unload_verified(identifier: str) -> None:
    """Unload `identifier` when done with it and prove nothing is left resident."""
    unload(identifier)
    ensure_none_loaded()
    logger.debug(f"unloaded {identifier}; residency verified empty")
