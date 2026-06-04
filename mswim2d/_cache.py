"""Download and local file-cache layer.

All MSWIM2D data products are served as plain static files. This module
downloads a file by its path relative to ``BASE_URL`` and caches the raw
bytes under the per-user cache directory, mirroring the remote layout.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import platformdirs
import requests

# Base URL of the MSWIM2D web host. Defaults to the production site; override
# with the MSWIM2D_BASE_URL environment variable (e.g. to point at a staging
# host). A trailing slash is tolerated.
BASE_URL = os.environ.get(
    "MSWIM2D_BASE_URL", "https://csem.engin.umich.edu/MSWIM2D"
).rstrip("/")

_TIMEOUT = 60


def cache_dir() -> Path:
    """Return (and create) the local cache directory."""
    d = Path(platformdirs.user_cache_dir("mswim2d"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_cached(rel: str, refresh: bool = False) -> Path:
    """Return a local path to a data file, downloading it if needed.

    Parameters
    ----------
    rel : str
        Path of the file relative to :data:`BASE_URL`, e.g.
        ``"precomputed_trajectories/chunks/Earth/2015.csv"``.
    refresh : bool, default False
        Re-download even if a cached copy already exists.

    Returns
    -------
    pathlib.Path
        Local path to the cached file.
    """
    path = cache_dir() / rel
    if path.exists() and not refresh:
        return path

    url = f"{BASE_URL}/{rel}"
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return path


def fetch_json(rel: str, refresh: bool = False) -> dict:
    """Download and parse a JSON manifest, caching the raw bytes."""
    path = ensure_cached(rel, refresh=refresh)
    with open(path, encoding="utf-8") as f:
        return json.load(f)
