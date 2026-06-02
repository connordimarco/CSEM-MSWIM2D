"""Tests for the 2-D field loader (offline, fixture-backed)."""

import numpy as np
import pytest

import mswim2d


class TestField:
    def test_shape_and_coords(self, patched):
        ds = mswim2d.get_field("1985-01-01T01:00:00")
        # One snapshot, (time, phi, r) = (1, n2, n1) = (1, 25, 75)
        assert ds["rho"].dims == ("time", "phi", "r")
        assert ds["rho"].shape == (1, 25, 75)
        assert list(ds.data_vars) == ["rho", "ux", "uy", "uz", "bx", "by", "bz", "p"]
        assert ds.attrs["product"] == "field"

    def test_axis_endpoints(self, patched):
        ds = mswim2d.get_field("1985-01-01T01:00:00")
        # phi is linear in [phiMin, phiMax]
        assert ds["phi"].values[0] == pytest.approx(1.8)
        assert ds["phi"].values[-1] == pytest.approx(347.4)
        # r = exp(linspace(radMin, radMax, n1)) -> endpoints rMin/rMax
        assert ds["r"].values[0] == pytest.approx(np.exp(0.007196), rel=1e-6)
        assert ds["r"].values[-1] == pytest.approx(np.exp(4.267117), rel=1e-6)
        assert ds["r"].values[0] < ds["r"].values[-1]

    def test_values_physical(self, patched):
        ds = mswim2d.get_field("1985-01-01T01:00:00")
        # Density should be finite and positive everywhere in the snapshot.
        rho = ds["rho"].values
        assert np.all(np.isfinite(rho))
        assert np.all(rho > 0)

    def test_range_query(self, patched):
        ds = mswim2d.get_field("1985-01-01T00:00:00", "1985-01-01T02:00:00")
        assert ds.sizes["time"] == 1
        assert str(ds.time.values[0])[:19] == "1985-01-01T01:00:00"

    def test_max_frames_guard(self, patched):
        with pytest.raises(ValueError, match="max_frames"):
            mswim2d.get_field("1985-01-01T00:00:00", "1985-01-02T00:00:00", max_frames=0)
