import pandas as pd

from ..core import utils
from . import sgutils


def read_tid(filnam, encoding="utf-8"):
    """Read data from an SBE 26plus Seagauge .tid file into an xarray dataset."""
    df = pd.read_csv(
        filnam,
        header=None,
        sep=r"\s+",
        names=["Sample", "Date", "Time", "P_1", "Temp"],
        parse_dates={"time": ["Date", "Time"]},
        encoding=encoding,
        index_col=False,
    )
    df.set_index("time", inplace=True)
    sg = df.to_xarray()
    return sg


def tid_to_cdf(metadata):
    """
    Load a raw .tid and .hex file and generate a .cdf file
    """
    basefile = metadata["basefile"]

    # Get metadata from .hex file
    hexmeta = sgutils.read_hex(basefile + ".hex")

    # Append to metadata variable
    metadata.update(hexmeta)

    # Read in data
    ds = read_tid(basefile + ".tid")

    # Convert pressure from psia to dbar
    ds["P_1"] = ds.P_1 / 14.503773800722 * 10

    ds = utils.write_metadata(ds, metadata)

    ds = utils.ensure_cf(ds)

    cdf_filename = ds.attrs["filename"] + "-tide-raw.cdf"

    ds.to_netcdf(cdf_filename, unlimited_dims=["time"])

    print(f"Finished writing data to {cdf_filename}")

    return ds