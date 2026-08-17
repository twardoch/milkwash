# this_file: milkwashy/src/milkwashy/cli.py
"""Fire CLI for milkwashy."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import fire
from loguru import logger
from rich.console import Console
from rich.table import Table

from . import lmsctl
from .config import config_path, load_config, write_default_config
from .indata import write_indata
from .pipeline import run_sweep
from .providers import list_models, resolve_endpoint
from .segment import plan_chunks

console = Console()


class Cli:
    """milkwashy — segment texts, rephrase chunks across local LLMs.

    Common flow:
        milkwashy init-config
        milkwashy gen-indata
        milkwashy models
        milkwashy run --limit 3 --max_size_mb 800
    """

    def __init__(self, project_dir: str = ".", verbose: bool = True):
        self._project = Path(project_dir).resolve()
        logger.remove()
        logger.add(sys.stderr, level="DEBUG" if verbose else "INFO")
        self._cfg = load_config()

    def init_config(self, force: bool = False):
        """Write the default TOML config to the platformdirs location."""
        path = write_default_config(force=force)
        console.print(f"config: [green]{path}[/green]")
        return str(path)

    def config_path(self):
        """Print the config file path."""
        console.print(str(config_path()))
        return str(config_path())

    def gen_indata(self):
        """Write the four seed texts into <project>/01-indata/."""
        written = write_indata(self._project / self._cfg.indata_dir)
        for lang, path in written:
            console.print(f"[cyan]{lang}[/cyan]  {path}")
        return [str(p) for _, p in written]

    def models(self, provider: str | None = None):
        """List models for a provider (default: config default_provider)."""
        prov = self._cfg.providers[provider or self._cfg.default_provider]
        endpoint = resolve_endpoint(prov)
        console.print(f"provider [bold]{prov.name}[/bold]  endpoint={endpoint}  lister={prov.lister}")
        models = list_models(prov)
        table = Table("size_bytes", "arch", "model_key")
        for m in models[:200]:
            table.add_row(str(m.size_bytes), m.arch or "-", m.key)
        console.print(table)
        console.print(f"[dim]{len(models)} models total[/dim]")
        return [m.key for m in models]

    def lms_status(self):
        """Show LM Studio server state and which models are resident."""
        running = lmsctl.server_status()
        console.print(f"server running: [bold]{running}[/bold]")
        resident = lmsctl.loaded() if running else []
        console.print(f"loaded models: {resident or '[dim]none[/dim]'}")
        return {"running": running, "loaded": resident}

    def lms_unload_all(self):
        """Unload every resident LM Studio model and verify none remain."""
        lmsctl.ensure_none_loaded()
        console.print("[green]no models loaded[/green]")

    def plan(self, provider: str | None = None):
        """Show the chunk plan (chunks + prompt) for each input text."""
        write_indata(self._project / self._cfg.indata_dir)
        for path in sorted((self._project / self._cfg.indata_dir).glob("*.txt")):
            lang = path.stem.split("__", 1)[0]
            plans = plan_chunks(path.read_text(encoding="utf-8"), lang,
                                min_sent=self._cfg.min_sentences, max_sent=self._cfg.max_sentences,
                                max_chars=self._cfg.max_chars)
            console.print(f"\n[bold]{path.name}[/bold]  ({lang})  {len(plans)} chunks")
            for cp in plans:
                console.print(f"  [{cp.index}] p{cp.prompt_index}: {cp.text[:70]!r}")

    def run(
        self,
        provider: str | None = None,
        limit: int | None = None,
        max_size_mb: float | None = None,
        manage_lms: bool = True,
        force: bool = False,
    ):
        """Run the full sweep. --limit N smallest models; --max_size_mb caps size.

        Existing output files are skipped by default, which is what makes a
        multi-hour sweep resumable; --force rewrites them.
        """
        prov = self._cfg.providers[provider or self._cfg.default_provider]
        max_bytes = int(max_size_mb * 1_000_000) if max_size_mb else None
        result = run_sweep(
            self._cfg, prov, project_dir=self._project,
            limit=limit, max_size_bytes=max_bytes, manage_lms=manage_lms,
            force=force,
        )
        # One flat line, so a wrapper script can grep the numbers. Returning the
        # dataclass instead would make Fire print its help page, not its values.
        summary = " ".join(f"{k}={v}" for k, v in asdict(result).items())
        console.print(f"[green]sweep {prov.name}: {summary}[/green]", soft_wrap=True)


def main():
    fire.Fire(Cli)


if __name__ == "__main__":
    main()
