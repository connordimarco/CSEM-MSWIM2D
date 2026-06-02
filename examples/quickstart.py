"""Minimal end-to-end example for the mswim2d client.

Run with network access:

    python examples/quickstart.py
"""

import mswim2d

# What is available?
print("bodies:", mswim2d.list_bodies())
print("inputs:", mswim2d.list_inputs())

# Model values along Earth's trajectory for January 2015.
traj = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-02-01")
print(traj)
mswim2d.to_csv(traj, "earth_jan2015.csv")
mswim2d.to_dat(traj, "earth_jan2015.dat")

# A single 2-D field snapshot near the 2015 St. Patrick's Day storm.
field = mswim2d.get_field("2015-03-17T00:00:00")
print(field)
mswim2d.to_csv(field, "field_20150317.csv")
# Or, with a netCDF backend installed (pip install netCDF4):
#   field.to_netcdf("field_20150317.nc")
