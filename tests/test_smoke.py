"""Live smoke tests that download from the MSWIM2D web host.

Skipped by default; run with ``pytest -m smoke`` (requires network access).
"""

import numpy as np
import pytest

import mswim2d

pytestmark = pytest.mark.smoke


def test_list_bodies_live():
    bodies = mswim2d.list_bodies()
    assert "Earth" in bodies
    assert len(bodies) > 5


def test_list_inputs_live():
    assert "l1" in mswim2d.list_inputs()


def test_get_trajectory_live():
    ds = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-01-03")
    assert ds.sizes["time"] > 24
    assert {"r_AU", "phi_deg", "rho", "bx"} <= set(ds.data_vars)
    assert np.isfinite(ds["rho"].values).any()


def test_get_input_live():
    ds = mswim2d.get_input("l1", "2015-01-01", "2015-01-03")
    assert ds.sizes["time"] > 24
    assert "Bx" in ds.data_vars


def test_get_field_live():
    ds = mswim2d.get_field("2015-03-17T00:00:00")
    assert ds["rho"].shape == (1, 25, 75)
    assert np.all(ds["rho"].values > 0)
    assert ds["r"].values[0] < ds["r"].values[-1]
