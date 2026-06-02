"""Tests for the trajectory/orbit/input loaders (offline, fixture-backed)."""

import numpy as np
import pytest

import mswim2d


def test_list_bodies(patched):
    assert mswim2d.list_bodies() == ["Earth"]


def test_list_inputs(patched):
    assert mswim2d.list_inputs() == ["l1", "solo"]


class TestTrajectory:
    def test_vars_and_attrs(self, patched):
        ds = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-01-02")
        assert "time" in ds.coords
        for v in ["r_AU", "phi_deg", "rho", "ux", "bx", "p", "ne4p"]:
            assert v in ds
        assert ds.attrs["product"] == "trajectory"
        assert ds.attrs["body"] == "Earth"
        assert ds.attrs["coordinate_system"] == "HGI"
        assert ds["bx"].attrs["units"] == "nT"
        assert ds["rho"].attrs["units"] == "amu/cm^3"

    def test_time_slicing_inclusive(self, patched):
        ds = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-01-02")
        assert ds.sizes["time"] == 25  # 00:00 day 1 .. 00:00 day 2, hourly
        assert str(ds.time.values[0])[:19] == "2015-01-01T00:00:00"
        assert str(ds.time.values[-1])[:19] == "2015-01-02T00:00:00"

    def test_unknown_body(self, patched):
        with pytest.raises(ValueError, match="Unknown body"):
            mswim2d.get_trajectory("Mars", "2015-01-01", "2015-01-02")

    def test_missing_year(self, patched):
        with pytest.raises(ValueError, match="no data for year"):
            mswim2d.get_trajectory("Earth", "2016-01-01", "2016-01-02")

    def test_start_after_end(self, patched):
        with pytest.raises(ValueError, match="must be <="):
            mswim2d.get_trajectory("Earth", "2015-01-02", "2015-01-01")


class TestOrbit:
    def test_vars_and_geometry(self, patched):
        ds = mswim2d.get_orbit("Earth", "2015-01-01", "2015-01-02")
        assert set(ds.data_vars) == {"r_AU", "phi_deg", "x_AU", "y_AU"}
        assert ds.attrs["product"] == "orbit"
        np.testing.assert_allclose(
            np.hypot(ds["x_AU"].values, ds["y_AU"].values),
            ds["r_AU"].values, rtol=1e-6,
        )


class TestInput:
    def test_l1_not_propagated(self, patched):
        ds = mswim2d.get_input("l1", "2015-01-01", "2015-01-02")
        for v in ["r", "lon", "Bx", "Ux", "rho", "T"]:
            assert v in ds
        assert "orig_r" not in ds.data_vars
        assert ds.attrs["product"] == "input"
        assert ds.attrs["propagated"] is False
        assert ds.sizes["time"] == 25

    def test_solo_propagated(self, patched):
        ds = mswim2d.get_input("solo", "2023-01-01", "2023-01-02")
        assert "orig_r" in ds.data_vars and "orig_lon" in ds.data_vars
        assert ds.attrs["propagated"] is True
        assert ds.sizes["time"] > 0

    def test_unknown_source(self, patched):
        with pytest.raises(ValueError, match="Unknown input source"):
            mswim2d.get_input("dscovr", "2015-01-01", "2015-01-02")
