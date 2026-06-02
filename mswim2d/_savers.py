"""Export MSWIM2D xarray Datasets to CSV and DAT formats.

The trajectory ``.dat`` writer reproduces the fixed-width layout the MSWIM2D
website produces (``MSWIM2D-Web/static/interpolate.js:formatOutput``), including
its JavaScript-style number formatting, so downloads match the web tool.
"""

from __future__ import annotations

import datetime
import math
from pathlib import Path

import pandas as pd
import xarray as xr

# Boltzmann constant in CGS (erg/K), matching interpolate.js KB_CGS. Used to
# derive ion temperature Ti = P / (kB * rho) from pressure and density.
_KB_CGS = 1.380649e-16

_ISO = "%Y-%m-%dT%H:%M:%S"


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def to_csv(ds: xr.Dataset, path: str | Path) -> None:
    """Write a MSWIM2D Dataset to CSV.

    1-D products (trajectory, orbit, input) are written with a ``datetime``
    index column; the 2-D ``field`` product is written in tidy long form with
    a ``(time, phi, r)`` index.
    """
    df = ds.to_dataframe()
    if not isinstance(df.index, pd.MultiIndex):
        df.index.name = "datetime"
    df.to_csv(path, date_format=_ISO)


# --------------------------------------------------------------------------- #
# JavaScript-compatible number formatting
# --------------------------------------------------------------------------- #
def _pad(s: str, w: int) -> str:
    """Mirror interpolate.js ``pad``: w<0 left-justifies, w>0 right-justifies."""
    if w < 0:
        return s + " " * max(0, -w - len(s))
    return " " * max(0, w - len(s)) + s


def _js_fixed(x: float, decimals: int) -> str:
    """Equivalent of JS ``Number.toFixed(decimals)`` (``"NaN"`` for NaN)."""
    if pd.isna(x):
        return "NaN"
    return f"{float(x):.{decimals}f}"


def _js_exp(x: float, decimals: int) -> str:
    """Equivalent of JS ``Number.toExponential(decimals)`` (no exp zero-pad)."""
    if pd.isna(x):
        return "NaN"
    mant, _, exp = f"{float(x):.{decimals}e}".partition("e")
    return f"{mant}e{exp[0]}{int(exp[1:])}"


def _js_round(x: float) -> int:
    """Equivalent of JS ``Math.round`` (round half toward +infinity)."""
    return int(math.floor(x + 0.5))


def _accessed() -> str:
    """Current UTC time formatted like the website 'Accessed' line."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _elapsed_hours(index: pd.DatetimeIndex) -> list[float]:
    """Elapsed hours of each timestamp since the first row."""
    if len(index) == 0:
        return []
    return list((index - index[0]).total_seconds() / 3600.0)


# --------------------------------------------------------------------------- #
# DAT — per-product writers
# --------------------------------------------------------------------------- #
def _to_dat_trajectory(ds: xr.Dataset, path: str | Path) -> None:
    df = ds.to_dataframe()
    idx = df.index
    hours = _elapsed_hours(idx)
    lines = [
        "MSWIM2D Model Interpolation",
        f"Accessed: {_accessed()}",
        f"Satellite: {ds.attrs.get('body', '')}",
        "Coordinate System: HGI",
        "Variables:",
        "  Date_Time: date and time in ISO format [UT]",
        "  hour: elapsed time since trajectory start [hr]",
        "  r: radial coordinate in HGI [AU]",
        "  phi: longitude coordinate in HGI [deg]",
        "  Rho: density [amu/cm^3]",
        "  Ux, Uy, Uz: bulk velocity components in HGI [km/s]",
        "  Bx, By, Bz: magnetic field components in HGI [nT]",
        "  Ti: ion temperature [K]",
        "",
        (_pad("Date_Time", -20) + _pad("hour", 7) + _pad("r", 7) + _pad("phi", 8)
         + _pad("Rho", 10) + _pad("Ux", 7) + _pad("Uy", 7) + _pad("Uz", 7)
         + _pad("Bx", 11) + _pad("By", 11) + _pad("Bz", 11) + _pad("Ti", 8)),
    ]
    for ts, (_, row), hr in zip(idx, df.iterrows(), hours):
        rho, p = row["rho"], row["p"]
        ti = "NaN" if pd.isna(p) or pd.isna(rho) else str(_js_round(p / (_KB_CGS * rho)))
        lines.append(
            _pad(pd.Timestamp(ts).strftime(_ISO), -20)
            + _pad(_js_fixed(hr, 1), 7)
            + _pad(_js_fixed(row["r_AU"], 3), 7)
            + _pad(_js_fixed(row["phi_deg"], 3), 8)
            + _pad(_js_fixed(rho, 5), 10)
            + _pad(_js_fixed(row["ux"], 1), 7)
            + _pad(_js_fixed(row["uy"], 1), 7)
            + _pad(_js_fixed(row["uz"], 1), 7)
            + _pad(_js_exp(row["bx"], 2), 11)
            + _pad(_js_exp(row["by"], 2), 11)
            + _pad(_js_exp(row["bz"], 2), 11)
            + _pad(ti, 8)
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _to_dat_orbit(ds: xr.Dataset, path: str | Path) -> None:
    df = ds.to_dataframe()
    idx = df.index
    hours = _elapsed_hours(idx)
    lines = [
        "MSWIM2D Body Orbit",
        f"Accessed: {_accessed()}",
        f"Satellite: {ds.attrs.get('body', '')}",
        "Coordinate System: HGI",
        "Variables:",
        "  Date_Time: date and time in ISO format [UT]",
        "  hour: elapsed time since start [hr]",
        "  r: radial coordinate in HGI [AU]",
        "  phi: longitude coordinate in HGI [deg]",
        "  x, y: Cartesian position in HGI [AU]",
        "",
        (_pad("Date_Time", -20) + _pad("hour", 8) + _pad("r", 9) + _pad("phi", 9)
         + _pad("x", 11) + _pad("y", 11)),
    ]
    for ts, (_, row), hr in zip(idx, df.iterrows(), hours):
        lines.append(
            _pad(pd.Timestamp(ts).strftime(_ISO), -20)
            + _pad(_js_fixed(hr, 1), 8)
            + _pad(_js_fixed(row["r_AU"], 4), 9)
            + _pad(_js_fixed(row["phi_deg"], 3), 9)
            + _pad(_js_fixed(row["x_AU"], 5), 11)
            + _pad(_js_fixed(row["y_AU"], 5), 11)
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# Input DAT column spec: (variable, field width, decimals).
_INPUT_DAT_SPEC: list[tuple[str, int, int]] = [
    ("r", 9, 4), ("lon", 9, 3),
    ("Bx", 10, 3), ("By", 10, 3), ("Bz", 10, 3),
    ("Ux", 10, 1), ("Uy", 10, 1), ("Uz", 10, 1),
    ("rho", 10, 3), ("T", 12, 0),
]
_INPUT_DAT_ORIG: list[tuple[str, int, int]] = [("orig_r", 10, 4), ("orig_lon", 10, 3)]


def _to_dat_input(ds: xr.Dataset, path: str | Path) -> None:
    df = ds.to_dataframe()
    spec = list(_INPUT_DAT_SPEC)
    if ds.attrs.get("propagated") and "orig_r" in df.columns:
        spec += _INPUT_DAT_ORIG
    lines = [
        "MSWIM2D In-Situ Input",
        f"Accessed: {_accessed()}",
        f"Source: {ds.attrs.get('satellite', '')}",
        "Coordinate System: HGI",
        "Units: AU, deg, nT, km/s, cm^-3, K",
        "",
        _pad("Date_Time", -20) + "".join(_pad(name, w) for name, w, _ in spec),
    ]
    for ts, (_, row) in zip(df.index, df.iterrows()):
        line = _pad(pd.Timestamp(ts).strftime(_ISO), -20)
        for name, w, dec in spec:
            line += _pad(_js_fixed(row[name], dec), w)
        lines.append(line)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def to_dat(ds: xr.Dataset, path: str | Path) -> None:
    """Write a MSWIM2D Dataset to a fixed-width ``.dat`` file.

    The output format is chosen from ``ds.attrs["product"]``:

    * ``"trajectory"`` — matches the MSWIM2D website download exactly.
    * ``"orbit"`` — Date_Time, hour, r, phi, x, y.
    * ``"input"`` — Date_Time and the in-situ variables (plus ``orig_*`` for
      propagated sources).
    * ``"field"`` — not supported (2-D); use ``ds.to_netcdf(...)`` instead.
    """
    product = ds.attrs.get("product")
    if product == "trajectory":
        _to_dat_trajectory(ds, path)
    elif product == "orbit":
        _to_dat_orbit(ds, path)
    elif product == "input":
        _to_dat_input(ds, path)
    elif product == "field":
        raise ValueError(
            "to_dat does not support 2-D field data; use ds.to_netcdf(...) instead."
        )
    else:
        raise ValueError(
            f"Dataset has unknown product {product!r}. "
            "Use a Dataset returned by a mswim2d loader."
        )
