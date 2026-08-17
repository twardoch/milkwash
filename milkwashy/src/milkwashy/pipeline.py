# this_file: milkwashy/src/milkwashy/pipeline.py
"""End-to-end sweep: for each model, rephrase every chunk of every input text.

Structure (requirement 9 — minimise LLM load/unload):
    for model in models (sorted by size asc):     # OUTER: load/probe once
        load model                                 # only via load_exclusive()
        for text in inputs:                        # INNER: reuse loaded model
            for chunk in plan(text):
                rephrase(chunk)
        unload model                               # try/finally, then verified

Exactly one model is resident at a time. `lmsctl.load_exclusive` proves via
`lms ps` that nothing is loaded before it loads, and the per-model body is
wrapped in try/finally so the unload also happens on skip, error, or interrupt.
If residency cannot be proven empty the sweep aborts rather than stacking a
second model on top of the first.

Resumable: a (model, text) whose output file already exists is skipped, so an
interrupted multi-hour sweep can be re-run to completion. A model whose outputs
all exist is not loaded at all.

Output layout: ``<outdata_dir>/<provider>/<filenamified-model-key>/<text>.txt``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from . import lmsctl
from .config import Config, Provider
from .indata import write_indata
from .inference import make_client, rephrase
from .naming import filenamify
from .providers import ModelInfo, list_models
from .segment import plan_chunks, plan_to_dicts


@dataclass
class SweepResult:
    models_total: int
    models_run: int
    models_skipped: int
    outputs_written: int
    outputs_resumed: int


def _skip_is_permanent(marker: Path) -> bool:
    """True if a recorded skip is a property of the model, not of the run."""
    try:
        return json.loads(marker.read_text(encoding="utf-8")).get("reason") == "load_failed"
    except (OSError, json.JSONDecodeError):
        return False


def _probe(client, model: str, cfg: Config) -> bool:
    """One tiny completion to confirm the model works as a chat LLM."""
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with: ok"}],
            max_tokens=8,
            temperature=0,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.info(f"{model}: probe failed, skipping ({str(exc)[:160]})")
        return False


def run_sweep(
    cfg: Config,
    provider: Provider,
    *,
    project_dir: Path,
    limit: int | None = None,
    max_size_bytes: int | None = None,
    manage_lms: bool = True,
    force: bool = False,
) -> SweepResult:
    """Sweep every model. Existing outputs are skipped unless `force`."""
    indata_dir = project_dir / cfg.indata_dir
    # Outputs are grouped by provider: 02-testllm/<provider>/<model>/<text>.txt.
    # Two providers can serve the same model name, so a flat model-keyed layout
    # would have them overwrite each other and silently mix corpora.
    outdata_dir = project_dir / cfg.outdata_dir / provider.name.lower()
    outdata_dir.mkdir(parents=True, exist_ok=True)

    # 1. ensure input texts exist
    inputs = write_indata(indata_dir)
    logger.info(f"{len(inputs)} input texts in {indata_dir}")

    # 2. precompute per-text chunk plans ONCE (shared across all models)
    plans: dict[str, tuple[str, list]] = {}  # stem -> (lang, chunk plans)
    for lang, path in inputs:
        text = path.read_text(encoding="utf-8")
        plans[path.stem] = (lang, plan_chunks(
            text, lang,
            min_sent=cfg.min_sentences, max_sent=cfg.max_sentences, max_chars=cfg.max_chars,
        ))

    # 3. enumerate models (sorted asc by size for lms)
    if provider.lister == "lms":
        # Issue step 4. The port is taken from the configured endpoint, because
        # a server brought up on a different port would list and load models
        # happily while every inference call went nowhere.
        parsed = urlparse(provider.endpoint)
        lmsctl.ensure_server(port=parsed.port, base_url=provider.endpoint)
    models: list[ModelInfo] = list_models(provider)
    if max_size_bytes is not None:
        models = [m for m in models if m.size_bytes == 0 or m.size_bytes <= max_size_bytes]
    if limit is not None:
        models = models[:limit]
    logger.info(f"provider={provider.name}: {len(models)} models to sweep")

    client = make_client(provider, cfg)
    if client is None:
        logger.error(f"provider {provider.name} unreachable; nothing to do")
        return SweepResult(len(models), 0, len(models), 0, 0)

    res = SweepResult(len(models), 0, 0, 0, 0)
    lms_managed = provider.lister == "lms" and manage_lms

    if lms_managed:
        # Anything left resident by an earlier run must go before we load.
        lmsctl.ensure_none_loaded()

    for mi in models:
        model_dir = outdata_dir / filenamify(mi.key)
        model_dir.mkdir(parents=True, exist_ok=True)

        # Default: an existing output file is left alone. That is what makes a
        # multi-hour sweep resumable, and it is why re-running is cheap.
        todo = [
            stem for stem in plans
            if force or not (model_dir / f"{stem}.txt").exists()
        ]

        skip_marker = model_dir / "_skipped.json"
        if skip_marker.exists() and not force and _skip_is_permanent(skip_marker):
            # `load_failed` is a property of the model (bad tensors, unsupported
            # architecture) and will not change between sweeps, so retrying costs
            # a pointless load every time. `probe_failed` is NOT treated this way:
            # a server on the wrong port or a transient outage marks every model
            # probe_failed, and honouring that would make the corrected re-run
            # skip the entire catalogue and report success having done nothing.
            res.models_skipped += 1
            logger.debug(f"[{mi.key}] previously failed to load; not retrying (use --force)")
            continue

        if not todo:
            # Fully resumed: loading this model would buy nothing (requirement 9).
            res.outputs_resumed += len(plans)
            res.models_run += 1
            logger.debug(f"[{mi.key}] all outputs present; not loading")
            continue
        res.outputs_resumed += len(plans) - len(todo)

        if lms_managed and not lmsctl.load_exclusive(mi.key):
            skip_marker.write_text(
                json.dumps({"model": mi.key, "reason": "load_failed"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            res.models_skipped += 1
            continue

        try:
            if not _probe(client, mi.key, cfg):
                skip_marker.write_text(
                    json.dumps({"model": mi.key, "reason": "probe_failed"}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                res.models_skipped += 1
                continue

            logger.info(f"[{mi.key}] size={mi.size_bytes} -> {model_dir.name}")
            for stem in todo:
                lang, chunk_plans = plans[stem]
                pieces: list[str] = []
                ok = True
                for cp in chunk_plans:
                    try:
                        pieces.append(rephrase(client, mi.key, cp.prompt, cp.text, cfg))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"[{mi.key}] {stem} chunk {cp.index} failed: {str(exc)[:140]}")
                        ok = False
                        break
                if not ok:
                    (model_dir / f"{stem}._error.json").write_text(
                        json.dumps({"model": mi.key, "text": stem, "reason": "chunk_failed"},
                                   ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    continue
                (model_dir / f"{stem}.txt").write_text("\n\n".join(pieces) + "\n", encoding="utf-8")
                (model_dir / f"{stem}.plan.json").write_text(
                    json.dumps({"model": mi.key, "language": lang, "chunks": plan_to_dicts(chunk_plans)},
                               ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                res.outputs_written += 1
            res.models_run += 1
        finally:
            # Runs on success, on `continue`, and on any exception or interrupt.
            if lms_managed:
                lmsctl.unload_verified(mi.key)

    logger.info(f"sweep done: {res}")
    return res
