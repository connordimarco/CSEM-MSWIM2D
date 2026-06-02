"""Shared fixtures: trimmed real data and patched manifest/cache layers."""

from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"

TRAJ_MANIFEST = {
    "vars": [
        "r_AU", "phi_deg", "rho", "ux", "uy", "uz", "bx", "by", "bz", "p",
        "neurho", "neuux", "neuuy", "neuuz", "neup",
        "ne4rho", "ne4ux", "ne4uy", "ne4uz", "ne4p",
    ],
    "bodies": {
        "Earth": {
            "years": [2015],
            "n_points": 72,
            "start": "2015-01-01T00:00:00",
            "end": "2015-01-03T23:00:00",
        },
    },
}

INPUT_MANIFEST = {
    "sources": [
        {"id": "l1", "label": "L1", "propagated": False, "years": [2015]},
        {"id": "solo", "label": "Solar Orbiter", "propagated": True, "years": [2023]},
    ],
}

FIELD_MANIFEST = {
    "grid": {
        "n1": 75, "n2": 25, "nVar": 8,
        "varNames": ["rho", "ux", "uy", "uz", "bx", "by", "bz", "p"],
        "radMin": 0.007196, "radMax": 4.267117,
        "phiMin": 1.8, "phiMax": 347.4,
    },
    "months": {"198501": ["1985-01-01T01:00:00"]},
}

# Map a remote relative path to its trimmed local fixture file.
_FIXTURE_MAP = {
    "precomputed_trajectories/chunks/Earth/2015.csv": "traj_Earth_2015.csv",
    "MSWIM2D_Data_New/Satellite_Data/chunks/l1/2015.csv": "input_l1_2015.csv",
    "MSWIM2D_Data_New/Satellite_Data/chunks/solo/2023.csv": "input_solo_2023.csv",
    "MSWIM2D_Data_New/snapshots_coarse/198501/0000.bin": "field_0000.bin",
}


def _fake_ensure_cached(rel, refresh=False):
    if rel not in _FIXTURE_MAP:
        raise FileNotFoundError(f"No fixture for {rel!r}")
    return DATA / _FIXTURE_MAP[rel]


@pytest.fixture
def patched(monkeypatch):
    """Patch loader's network/manifest access to use local fixtures."""
    import mswim2d._loader as loader
    import mswim2d._manifest as manifest

    monkeypatch.setattr(loader, "ensure_cached", _fake_ensure_cached)
    monkeypatch.setattr(manifest, "trajectory_manifest", lambda refresh=False: TRAJ_MANIFEST)
    monkeypatch.setattr(manifest, "input_manifest", lambda refresh=False: INPUT_MANIFEST)
    monkeypatch.setattr(manifest, "field_manifest", lambda refresh=False: FIELD_MANIFEST)
