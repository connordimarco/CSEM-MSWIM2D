# CSEM-MSWIM2D

Python client for the [MSWIM2D solar wind model](https://csem.engin.umich.edu/MSWIM2D/) -
a 2-D MHD model of the heliospheric equatorial plane, driven by in-situ
observations and propagated outward to the orbits of the planets and deep-space
spacecraft.

All data products are served as static files and returned as
[xarray](https://docs.xarray.dev/) Datasets, cached locally after first download.

## Install

```
pip install csem-mswim2d
```

## Quickstart

Model values sampled along a body's trajectory:

```python
import mswim2d

mswim2d.list_bodies()
# ['Cassini', 'Earth', 'Galileo', 'Juno', 'Jupiter', ... 'Voyager1', 'Voyager2']

data = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-02-01")
print(data)
```

```
<xarray.Dataset>
Dimensions:  (time: 745)
Coordinates:
  * time     (time) datetime64[ns] 2015-01-01 ... 2015-02-01
Data variables:
    r_AU     (time) float64 ...   # heliocentric radius [AU, HGI]
    phi_deg  (time) float64 ...   # heliocentric longitude [deg, HGI]
    rho      (time) float64 ...   # density [amu/cm^3]
    ux, uy, uz   (time) float64 ...   # bulk velocity [km/s, HGI]
    bx, by, bz   (time) float64 ...   # magnetic field [nT, HGI]
    p        (time) float64 ...   # thermal pressure [erg/cm^3]
    neurho ... ne4p   (time) float64 ...   # neutral-hydrogen populations
Attributes:
    source:             MSWIM2D
    url:                https://csem.engin.umich.edu/MSWIM2D/
    body:               Earth
    coordinate_system:  HGI
    product:            trajectory
```

## More products

```python
# A body's position (r, phi, and Cartesian x/y in AU)
mswim2d.get_orbit("Voyager1", "2010-01-01", "2012-01-01")

# The in-situ inputs that drive the model
mswim2d.list_inputs()          # ['l1', 'stereoA', 'stereoB', 'solo']
mswim2d.get_input("l1", "2015-01-01", "2015-02-01")
mswim2d.get_input("solo", "2023-01-01", "2023-02-01")   # propagated -> orig_r/orig_lon

# 2-D field snapshots of the equatorial plane, dims (time, phi, r)
mswim2d.get_field("2015-03-17T00:00:00")                         # nearest single frame
mswim2d.get_field("2015-03-17T00:00:00", "2015-03-18T00:00:00")  # all frames in range
```

The base URL defaults to the staging host; override it with the
`MSWIM2D_BASE_URL` environment variable.

## Saving to file

```python
data = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-02-01")
mswim2d.to_csv(data, "earth.csv")
mswim2d.to_dat(data, "earth.dat")   # matches the website download format
```

`to_dat` chooses its layout from the dataset's `product` attribute (trajectory,
orbit, or input). The 2-D `field` product has no `.dat` form — save it with
`mswim2d.to_csv` (tidy long form), or `field.to_netcdf("field.nc")` if you have a
netCDF backend installed (`pip install netCDF4` or `h5netcdf`). Data is cached
locally after the first download.

## Using with spacepy

MSWIM2D Datasets convert to a [spacepy](https://spacepy.github.io/) `SpaceData`
in a few lines:

```python
import mswim2d
from spacepy.datamodel import SpaceData, dmarray

ds = mswim2d.get_trajectory("Earth", "2015-01-01", "2015-02-01")

sd = SpaceData(attrs=dict(ds.attrs))
sd["Epoch"] = dmarray(ds["time"].values, attrs={"units": "UTC"})
for name, da in ds.data_vars.items():
    sd[name] = dmarray(da.values, attrs=dict(da.attrs))
```

## Not yet supported

- Interpolation along **custom / uploaded trajectories** (the website's dynamic
  `interpolate.php` path). Only the precomputed bodies are available here.

## See also

- [MSWIM2D](https://csem.engin.umich.edu/MSWIM2D/) - the model and interactive web tool
- [CSEM-MIDL](https://github.com/connordimarco/CSEM-MIDL) - companion client for the
  MIDL solar wind dataset (the L1 inputs to this model)
