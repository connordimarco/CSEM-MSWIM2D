"""Accessors for the three MSWIM2D product manifests.

Each data product on the web host publishes a JSON manifest describing its
contents (available bodies/years, in-situ sources, or snapshot grid + times).
These are small (except the field manifest) and cached like any other file.
"""

from __future__ import annotations

from mswim2d._cache import fetch_json

TRAJ_MANIFEST = "precomputed_trajectories/chunks/manifest.json"
INPUT_MANIFEST = "MSWIM2D_Data_New/Satellite_Data/chunks/manifest.json"
FIELD_MANIFEST = "MSWIM2D_Data_New/snapshots_coarse/manifest.json"


def trajectory_manifest(refresh: bool = False) -> dict:
    """Return the precomputed-trajectory manifest (``vars`` + ``bodies``)."""
    return fetch_json(TRAJ_MANIFEST, refresh=refresh)


def input_manifest(refresh: bool = False) -> dict:
    """Return the in-situ input manifest (``sources``)."""
    return fetch_json(INPUT_MANIFEST, refresh=refresh)


def field_manifest(refresh: bool = False) -> dict:
    """Return the 2-D field-snapshot manifest (``grid`` + ``months``)."""
    return fetch_json(FIELD_MANIFEST, refresh=refresh)
