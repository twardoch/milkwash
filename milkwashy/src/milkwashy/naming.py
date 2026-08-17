# this_file: milkwashy/src/milkwashy/naming.py
"""Filesystem-safe name generation (verbatim from issue spec)."""

import hashlib

from pathvalidate import sanitize_filename
from slugify import slugify

RESERVED = {"con", "prn", "aux", "nul", *(f"{p}{i}" for p in ("com", "lpt") for i in range(1, 10))}


def filenamify(text: str, ext: str = "", *, sep: str = "-", max_bytes: int = 255) -> str:
    raw, ext = str(text).strip(), ext and ("." + ext.lstrip("."))
    stem = slugify(raw, separator=sep)
    tag = sep + hashlib.blake2b(raw.encode(), digest_size=3).hexdigest() if stem != raw else ""
    stem = stem.encode()[: max(max_bytes - len((tag + ext).encode()), 0)].decode("utf-8", "ignore").strip(sep)
    stem = f"file{sep}{stem}" if stem.lower() in RESERVED else stem or "untitled"
    return sanitize_filename(stem + tag + ext, platform="universal", replacement_text=sep)
