"""Load MSWIM2D data from the web host into xarray Datasets.

Three products are exposed, all returned as :class:`xarray.Dataset`:

* :func:`get_trajectory` / :func:`get_orbit` — model values (and HGI position)
  sampled hourly along a body's path through the MSWIM2D domain.
* :func:`get_input` — the in-situ time series that drive the model (L1, STEREO,
  Solar Orbiter).
* :func:`get_field` — 2-D plasma snapshots of the heliospheric equatorial plane.

Files are downloaded on first access and cached locally; subsequent calls for
the same years/snapshots are served from cache.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from mswim2d import _manifest
from mswim2d._cache import BASE_URL, ensure_cached
from mswim2d._time import Timelike, months_in_range, parse_timestamp, years_in_range

_TRAJ_DIR = "precomputed_trajectories/chunks"
_INPUT_DIR = "MSWIM2D_Data_New/Satellite_Data/chunks"
_FIELD_DIR = "MSWIM2D_Data_New/snapshots_coarse"

# Default ceiling on the number of field snapshots one call may load, to avoid
# silently pulling tens of thousands of frames (each ~60 KB).
_DEFAULT_MAX_FRAMES = 240

_HGI = "HGI"

_TRAJ_VAR_ATTRS: dict[str, dict[str, str]] = {
    "r_AU": {"units": "AU", "long_name": "Heliocentric radius", "coordinate_system": _HGI},
    "phi_deg": {"units": "deg", "long_name": "Heliocentric longitude", "coordinate_system": _HGI},
    "rho": {"units": "amu/cm^3", "long_name": "Solar wind density"},
    "ux": {"units": "km/s", "long_name": "Bulk velocity X", "coordinate_system": _HGI},
    "uy": {"units": "km/s", "long_name": "Bulk velocity Y", "coordinate_system": _HGI},
    "uz": {"units": "km/s", "long_name": "Bulk velocity Z", "coordinate_system": _HGI},
    "bx": {"units": "nT", "long_name": "Magnetic field X", "coordinate_system": _HGI},
    "by": {"units": "nT", "long_name": "Magnetic field Y", "coordinate_system": _HGI},
    "bz": {"units": "nT", "long_name": "Magnetic field Z", "coordinate_system": _HGI},
    "p": {"units": "erg/cm^3", "long_name": "Thermal pressure"},
    "neurho": {"units": "amu/cm^3", "long_name": "Neutral H density (population 1)"},
    "neuux": {"units": "km/s", "long_name": "Neutral H velocity X (population 1)", "coordinate_system": _HGI},
    "neuuy": {"units": "km/s", "long_name": "Neutral H velocity Y (population 1)", "coordinate_system": _HGI},
    "neuuz": {"units": "km/s", "long_name": "Neutral H velocity Z (population 1)", "coordinate_system": _HGI},
    "neup": {"units": "erg/cm^3", "long_name": "Neutral H pressure (population 1)"},
    "ne4rho": {"units": "amu/cm^3", "long_name": "Neutral H density (population 4)"},
    "ne4ux": {"units": "km/s", "long_name": "Neutral H velocity X (population 4)", "coordinate_system": _HGI},
    "ne4uy": {"units": "km/s", "long_name": "Neutral H velocity Y (population 4)", "coordinate_system": _HGI},
    "ne4uz": {"units": "km/s", "long_name": "Neutral H velocity Z (population 4)", "coordinate_system": _HGI},
    "ne4p": {"units": "erg/cm^3", "long_name": "Neutral H pressure (population 4)"},
}

_INPUT_VAR_ATTRS: dict[str, dict[str, str]] = {
    "r": {"units": "AU", "long_name": "Heliocentric radius", "coordinate_system": _HGI},
    "lon": {"units": "deg", "long_name": "Heliocentric longitude", "coordinate_system": _HGI},
    "Bx": {"units": "nT", "long_name": "Magnetic field X", "coordinate_system": _HGI},
    "By": {"units": "nT", "long_name": "Magnetic field Y", "coordinate_system": _HGI},
    "Bz": {"units": "nT", "long_name": "Magnetic field Z", "coordinate_system": _HGI},
    "Ux": {"units": "km/s", "long_name": "Bulk velocity X", "coordinate_system": _HGI},
    "Uy": {"units": "km/s", "long_name": "Bulk velocity Y", "coordinate_system": _HGI},
    "Uz": {"units": "km/s", "long_name": "Bulk velocity Z", "coordinate_system": _HGI},
    "rho": {"units": "cm^-3", "long_name": "Proton number density"},
    "T": {"units": "K", "long_name": "Proton temperature"},
    "orig_r": {"units": "AU", "long_name": "Original (un-propagated) radius", "coordinate_system": _HGI},
    "orig_lon": {"units": "deg", "long_name": "Original (un-propagated) longitude", "coordinate_system": _HGI},
}

_FIELD_VAR_ATTRS: dict[str, dict[str, str]] = {
    "rho": {"units": "amu/cm^3", "long_name": "Solar wind density"},
    "ux": {"units": "km/s", "long_name": "Bulk velocity X", "coordinate_system": _HGI},
    "uy": {"units": "km/s", "long_name": "Bulk velocity Y", "coordinate_system": _HGI},
    "uz": {"units": "km/s", "long_name": "Bulk velocity Z", "coordinate_system": _HGI},
    "bx": {"units": "nT", "long_name": "Magnetic field X", "coordinate_system": _HGI},
    "by": {"units": "nT", "long_name": "Magnetic field Y", "coordinate_system": _HGI},
    "bz": {"units": "nT", "long_name": "Magnetic field Z", "coordinate_system": _HGI},
    "p": {"units": "erg/cm^3", "long_name": "Thermal pressure"},
}


# --------------------------------------------------------------------------- #
# Catalog helpers
# --------------------------------------------------------------------------- #
def list_bodies() -> list[str]:
    """Return the sorted list of bodies with precomputed trajectories."""
    return sorted(_manifest.trajectory_manifest()["bodies"])


def list_inputs() -> list[str]:
    """Return the list of in-situ input source IDs (e.g. ``"l1"``)."""
    return [s["id"] for s in _manifest.input_manifest()["sources"]]


# --------------------------------------------------------------------------- #
# Shared CSV machinery
# --------------------------------------------------------------------------- #
def _read_csv(path: Path) -> pd.DataFrame:
    """Read a single cached yearly CSV (time-indexed on ``datetime``)."""
    return pd.read_csv(path, parse_dates=["datetime"], index_col="datetime")


def _resolve_window(
    start: Timelike,
    end: Timelike,
    available: set[int],
    label: str,
    coverage: str,
) -> tuple[pd.Timestamp, pd.Timestamp, list[int]]:
    """Validate a time window and return (start_ts, end_ts, requested years)."""
    start_ts = parse_timestamp(start)
    end_ts = parse_timestamp(end)
    if start_ts > end_ts:
        raise ValueError(f"start ({start_ts}) must be <= end ({end_ts})")
    requested = years_in_range(start_ts, end_ts)
    missing = [y for y in requested if y not in available]
    if missing:
        raise ValueError(
            f"{label} has no data for year(s) {missing}. Coverage: {coverage}."
        )
    return start_ts, end_ts, requested


def _load_years(rel_dir: str, years: list[int], start_ts, end_ts) -> pd.DataFrame:
    """Read and concatenate yearly CSVs spanning ``[start_ts, end_ts]``."""
    frames = [_read_csv(ensure_cached(f"{rel_dir}/{y}.csv")) for y in years]
    df = pd.concat(frames).sort_index()
    return df.loc[start_ts:end_ts]


def _to_dataset(df: pd.DataFrame, var_attrs: dict[str, dict[str, str]]) -> xr.Dataset:
    """Convert a ``datetime``-indexed DataFrame to a Dataset with var metadata."""
    ds = df.to_xarray().rename({"datetime": "time"})
    for var, attrs in var_attrs.items():
        if var in ds:
            ds[var].attrs.update(attrs)
    return ds


# --------------------------------------------------------------------------- #
# Trajectories
# --------------------------------------------------------------------------- #
def get_trajectory(body: str, start: Timelike, end: Timelike) -> xr.Dataset:
    """Load model values sampled along a body's trajectory.

    Parameters
    ----------
    body : str
        Body name as listed by :func:`list_bodies` (e.g. ``"Earth"``,
        ``"Voyager1"``, ``"STEREO-A"``).
    start, end : str, datetime, numpy.datetime64, or pandas.Timestamp
        Inclusive time-range bounds (ISO 8601 strings accepted).

    Returns
    -------
    xarray.Dataset
        Dataset with a ``time`` coordinate and the model variables
        (``r_AU``, ``phi_deg``, ``rho``, ``ux/uy/uz``, ``bx/by/bz``, ``p``,
        plus neutral-hydrogen populations).
    """
    man = _manifest.trajectory_manifest()
    bodies = man["bodies"]
    if body not in bodies:
        raise ValueError(
            f"Unknown body {body!r}. Available: {sorted(bodies)}"
        )
    info = bodies[body]
    start_ts, end_ts, years = _resolve_window(
        start, end, set(info["years"]), repr(body),
        f"{info['start']} to {info['end']}",
    )
    df = _load_years(f"{_TRAJ_DIR}/{body}", years, start_ts, end_ts)
    ds = _to_dataset(df, _TRAJ_VAR_ATTRS)
    ds.attrs.update(
        source="MSWIM2D", url=BASE_URL, body=body,
        coordinate_system=_HGI, product="trajectory",
    )
    return ds


def get_orbit(body: str, start: Timelike, end: Timelike) -> xr.Dataset:
    """Load a body's heliocentric position along its trajectory.

    Returns the radial/longitudinal coordinates plus Cartesian HGI
    ``x_AU``/``y_AU`` derived from them, without the model plasma variables.
    """
    traj = get_trajectory(body, start, end)
    ds = traj[["r_AU", "phi_deg"]]
    phi = np.deg2rad(ds["phi_deg"])
    ds["x_AU"] = ds["r_AU"] * np.cos(phi)
    ds["y_AU"] = ds["r_AU"] * np.sin(phi)
    ds["x_AU"].attrs = {"units": "AU", "long_name": "Heliocentric X", "coordinate_system": _HGI}
    ds["y_AU"].attrs = {"units": "AU", "long_name": "Heliocentric Y", "coordinate_system": _HGI}
    ds.attrs = dict(traj.attrs)
    ds.attrs["product"] = "orbit"
    return ds


# --------------------------------------------------------------------------- #
# In-situ inputs
# --------------------------------------------------------------------------- #
def get_input(source: str, start: Timelike, end: Timelike) -> xr.Dataset:
    """Load an in-situ input time series.

    Parameters
    ----------
    source : str
        Source ID from :func:`list_inputs` (``"l1"``, ``"stereoA"``,
        ``"stereoB"``, ``"solo"``).
    start, end : str, datetime, numpy.datetime64, or pandas.Timestamp
        Inclusive time-range bounds.

    Returns
    -------
    xarray.Dataset
        Dataset with a ``time`` coordinate and ``r``, ``lon``, ``Bx/By/Bz``,
        ``Ux/Uy/Uz``, ``rho``, ``T`` (plus ``orig_r``/``orig_lon`` for
        propagated sources).
    """
    man = _manifest.input_manifest()
    sources = {s["id"]: s for s in man["sources"]}
    if source not in sources:
        raise ValueError(
            f"Unknown input source {source!r}. Available: {list(sources)}"
        )
    info = sources[source]
    yrs = info["years"]
    start_ts, end_ts, years = _resolve_window(
        start, end, set(yrs), repr(source),
        f"{min(yrs)} to {max(yrs)}",
    )
    df = _load_years(f"{_INPUT_DIR}/{source}", years, start_ts, end_ts)
    ds = _to_dataset(df, _INPUT_VAR_ATTRS)
    ds.attrs.update(
        source="MSWIM2D", url=BASE_URL, satellite=source,
        coordinate_system=_HGI, product="input",
        propagated=bool(info.get("propagated", False)),
    )
    return ds


# --------------------------------------------------------------------------- #
# 2-D field snapshots
# --------------------------------------------------------------------------- #
def _grid_axes(grid: dict) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct the (r, phi) physical axes from the grid metadata."""
    n1, n2 = grid["n1"], grid["n2"]
    r = np.exp(np.linspace(grid["radMin"], grid["radMax"], n1))
    phi = np.linspace(grid["phiMin"], grid["phiMax"], n2)
    return r, phi


def _select_snapshots(
    months: dict, start_ts: pd.Timestamp, end_ts: pd.Timestamp | None
) -> list[tuple[str, int, pd.Timestamp]]:
    """Return ``(month, idx, timestamp)`` for snapshots in the requested window.

    With ``end_ts is None`` the single snapshot nearest ``start_ts`` is returned.
    """
    if end_ts is None:
        # Restrict the nearest-search to the target month and its neighbours;
        # fall back to a full scan only if none of those exist.
        keys = [
            f"{(start_ts + pd.DateOffset(months=k)).year:04d}"
            f"{(start_ts + pd.DateOffset(months=k)).month:02d}"
            for k in (-1, 0, 1)
        ]
        candidates = [m for m in keys if m in months] or list(months)
        best: tuple | None = None
        for month in candidates:
            for idx, iso in enumerate(months[month]):
                ts = parse_timestamp(iso)
                delta = abs(ts - start_ts)
                if best is None or delta < best[0]:
                    best = (delta, month, idx, ts)
        if best is None:
            raise ValueError("Field manifest contains no snapshots.")
        return [(best[1], best[2], best[3])]

    selected: list[tuple[str, int, pd.Timestamp]] = []
    for month in months_in_range(start_ts, end_ts):
        for idx, iso in enumerate(months.get(month, [])):
            ts = parse_timestamp(iso)
            if start_ts <= ts <= end_ts:
                selected.append((month, idx, ts))
    selected.sort(key=lambda e: e[2])
    return selected


def get_field(
    start: Timelike,
    end: Timelike | None = None,
    max_frames: int = _DEFAULT_MAX_FRAMES,
) -> xr.Dataset:
    """Load 2-D plasma snapshots of the heliospheric equatorial plane.

    Parameters
    ----------
    start : str, datetime, numpy.datetime64, or pandas.Timestamp
        Window start. If ``end`` is ``None``, the single snapshot nearest
        this time is returned.
    end : same types or None, optional
        Window end (inclusive). All snapshots in ``[start, end]`` are loaded.
    max_frames : int, default 240
        Raise ``ValueError`` if the window selects more than this many
        snapshots, rather than silently downloading a huge number of frames.

    Returns
    -------
    xarray.Dataset
        Dataset with dims ``(time, phi, r)``, coordinates ``time`` (UT),
        ``phi`` [deg, HGI] and ``r`` [AU, HGI], and data variables
        ``rho``, ``ux/uy/uz``, ``bx/by/bz``, ``p``.
    """
    man = _manifest.field_manifest()
    grid = man["grid"]
    n1, n2, nvar = grid["n1"], grid["n2"], grid["nVar"]
    varnames = grid["varNames"]
    stride = n1 * n2

    start_ts = parse_timestamp(start)
    end_ts = parse_timestamp(end) if end is not None else None
    if end_ts is not None and start_ts > end_ts:
        raise ValueError(f"start ({start_ts}) must be <= end ({end_ts})")

    selected = _select_snapshots(man["months"], start_ts, end_ts)
    if not selected:
        raise ValueError(f"No field snapshots found in [{start_ts}, {end_ts}].")
    if len(selected) > max_frames:
        raise ValueError(
            f"Window selects {len(selected)} snapshots (> max_frames={max_frames}). "
            "Narrow the time range or raise max_frames."
        )

    data = np.empty((len(selected), nvar, n2, n1), dtype="float32")
    times: list[pd.Timestamp] = []
    for k, (month, idx, ts) in enumerate(selected):
        path = ensure_cached(f"{_FIELD_DIR}/{month}/{idx:04d}.bin")
        raw = np.frombuffer(path.read_bytes(), dtype="<f4")
        # Each variable is a stride-long block; within a block the flat index
        # is i + j*n1 (i radial, j azimuthal) -> reshape to (phi, r).
        data[k] = raw.reshape(nvar, n2, n1)
        times.append(ts)

    r, phi = _grid_axes(grid)
    ds = xr.Dataset(
        coords={"time": pd.DatetimeIndex(times), "phi": phi, "r": r},
    )
    for v, name in enumerate(varnames):
        ds[name] = (("time", "phi", "r"), data[:, v, :, :])
        ds[name].attrs.update(_FIELD_VAR_ATTRS.get(name, {}))
    ds["r"].attrs = {"units": "AU", "long_name": "Heliocentric radius", "coordinate_system": _HGI}
    ds["phi"].attrs = {"units": "deg", "long_name": "Heliocentric longitude", "coordinate_system": _HGI}
    ds.attrs.update(
        source="MSWIM2D", url=BASE_URL, coordinate_system=_HGI, product="field",
        n1=n1, n2=n2,
        radMin=grid["radMin"], radMax=grid["radMax"],
        phiMin=grid["phiMin"], phiMax=grid["phiMax"],
    )
    return ds
