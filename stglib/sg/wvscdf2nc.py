import xarray as xr

from ..core import utils
from . import sgutils


def cdf_to_nc(cdf_filename, atmpres=None):
    """
    Load a raw .cdf file and generate a processed .nc file
    """

    # Load raw .cdf data
    ds = xr.open_dataset(cdf_filename)

    # remove units in case we change and we can use larger time steps
    ds.time.encoding.pop("units")

    # Drop sample variable
    ds = ds.drop_vars("burst_number")

    # Atmospheric pressure correction
    if atmpres is not None:
        ds = sgutils.atmos_correct(ds, atmpres)

    # Add attributes
    ds = sgutils.ds_add_attrs(ds)

    # Call QAQC
    ds = sgutils.sg_qaqc(ds)

    # Run utilities
    ds = utils.clip_ds(ds)
    ds = utils.ds_add_lat_lon(ds)
    ds = utils.create_nominal_instrument_depth(ds)
    ds = utils.create_z(ds)
    ds = utils.add_start_stop_time(ds)
    ds = utils.add_min_max(ds)
    ds = utils.add_delta_t(ds)

    # Write to .nc file
    print("Writing cleaned/trimmed data to .nc file")
    nc_filename = ds.attrs["filename"] + "r-a.nc"

    ds.to_netcdf(
        nc_filename, unlimited_dims=["time"], encoding={"time": {"dtype": "i4"}}
    )
    utils.check_compliance(nc_filename, conventions=ds.attrs["Conventions"])

    print(f"Done writing netCDF file {nc_filename}")