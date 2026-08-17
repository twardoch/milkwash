# this_file: milkwashy/src/milkwashy/__init__.py
"""milkwashy: text-laundering pipeline over many local OpenAI-compatible LLMs."""

from .config import Config, Provider, load_config, write_default_config
from .segment import PROMPTS, ChunkPlan, plan_chunks, segment_sentences, text_seed
from .pipeline import SweepResult, run_sweep

__version__ = "1.0.0"

__all__ = [
    "Config",
    "Provider",
    "load_config",
    "write_default_config",
    "PROMPTS",
    "ChunkPlan",
    "plan_chunks",
    "segment_sentences",
    "text_seed",
    "SweepResult",
    "run_sweep",
]
