"""Tests for mswim2d._savers (to_csv / to_dat)."""

import math

import pandas as pd
import pytest

import mswim2d
from mswim2d._savers import _js_exp, _js_fixed, _js_round, _pad

_KB_CGS = 1.380649e-16


# --- JS-compatible formatting primitives ---
class TestJsFormatting:
    def test_pad_right_and_left(self):
        assert _pad("x", 5) == "    x"
        assert _pad("x", -5) == "x    "
        assert _pad("toolong", 3) == "toolong"  # no truncation

    def test_js_exp_no_exponent_zero_pad(self):
        assert _js_exp(-4.703798, 2) == "-4.70e+0"   # not -4.70e+00
        assert _js_exp(1360.5, 2) == "1.36e+3"
        assert _js_exp(5.05e-16, 2) == "5.05e-16"
        assert _js_exp(0.0, 2) == "0.00e+0"
        assert _js_exp(float("nan"), 2) == "NaN"

    def test_js_fixed(self):
        assert _js_fixed(3.573208, 5) == "3.57321"
        assert _js_fixed(float("nan"), 1) == "NaN"

    def test_js_round_half_up(self):
        assert _js_round(2.5) == 3
        assert _js_round(2.4) == 2


class TestToCsv:
    def test_trajectory_roundtrip(self, patched, tmp_path):
        ds = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-01-02")
        out = tmp_path / "t.csv"
        mswim2d.to_csv(ds, out)
        df = pd.read_csv(out, parse_dates=["datetime"], index_col="datetime")
        assert len(df) == 25
        assert "rho" in df.columns
        with open(out) as f:
            lines = f.readlines()
        assert lines[0].split(",")[0] == "datetime"
        assert "2015-01-01T00:00:00" in lines[1]

    def test_field_long_form(self, patched, tmp_path):
        ds = mswim2d.get_field("1985-01-01T01:00:00")
        out = tmp_path / "f.csv"
        mswim2d.to_csv(ds, out)
        header = open(out).readline().strip().split(",")
        assert header[:3] == ["time", "phi", "r"]
        assert "rho" in header


class TestToDatTrajectory:
    def test_header(self, patched, tmp_path):
        ds = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-01-02")
        out = tmp_path / "t.dat"
        mswim2d.to_dat(ds, out)
        lines = open(out).read().splitlines()
        assert lines[0] == "MSWIM2D Model Interpolation"
        assert lines[2] == "Satellite: Earth"
        assert "Coordinate System: HGI" in lines
        col_header = [l for l in lines if l.startswith("Date_Time")][0]
        for c in ["hour", "r", "phi", "Rho", "Ux", "Bx", "Ti"]:
            assert c in col_header

    def test_first_data_row_matches_website_formula(self, patched, tmp_path):
        ds = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-01-02")
        out = tmp_path / "t.dat"
        mswim2d.to_dat(ds, out)
        data_lines = [l for l in open(out).read().splitlines()
                      if l.startswith("2015-01-01T00:00:00")]
        first = data_lines[0]
        # JS-style exponent (single exponent digit), elapsed hour 0.0
        assert first.startswith("2015-01-01T00:00:00 ")
        assert "-4.70e+0" in first and "-4.70e+00" not in first
        # Ti = round(p / (kB * rho)) from the fixture's first row.
        rho = float(ds["rho"].values[0])
        p = float(ds["p"].values[0])
        expected_ti = str(int(math.floor(p / (_KB_CGS * rho) + 0.5)))
        assert first.rstrip().endswith(expected_ti)


class TestToDatOther:
    def test_orbit(self, patched, tmp_path):
        ds = mswim2d.get_orbit("Earth", "2015-01-01", "2015-01-02")
        out = tmp_path / "o.dat"
        mswim2d.to_dat(ds, out)
        lines = open(out).read().splitlines()
        assert lines[0] == "MSWIM2D Body Orbit"
        col_header = [l for l in lines if l.startswith("Date_Time")][0]
        for c in ["hour", "r", "phi", "x", "y"]:
            assert c in col_header

    def test_input_propagated_has_orig_cols(self, patched, tmp_path):
        ds = mswim2d.get_input("solo", "2023-01-01", "2023-01-02")
        out = tmp_path / "i.dat"
        mswim2d.to_dat(ds, out)
        col_header = [l for l in open(out).read().splitlines()
                      if l.startswith("Date_Time")][0]
        assert "orig_r" in col_header and "orig_lon" in col_header

    def test_field_raises(self, patched, tmp_path):
        ds = mswim2d.get_field("1985-01-01T01:00:00")
        with pytest.raises(ValueError, match="does not support 2-D field"):
            mswim2d.to_dat(ds, tmp_path / "f.dat")

    def test_unknown_product_raises(self, tmp_path):
        import xarray as xr
        ds = xr.Dataset({"a": ("time", [1, 2])}, coords={"time": [0, 1]})
        with pytest.raises(ValueError, match="unknown product"):
            mswim2d.to_dat(ds, tmp_path / "x.dat")
