"""mswim2d - Python client for the MSWIM2D solar wind model."""

from mswim2d._loader import (
    get_field,
    get_input,
    get_orbit,
    get_trajectory,
    list_bodies,
    list_inputs,
)
from mswim2d._savers import to_csv, to_dat

__all__ = [
    "get_trajectory",
    "get_orbit",
    "get_input",
    "get_field",
    "list_bodies",
    "list_inputs",
    "to_csv",
    "to_dat",
]
__version__ = "0.1.0"
