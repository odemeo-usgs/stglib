import datetime as dt
import glob
import re
import time
import warnings

import numpy as np
import pandas as pd
import scipy.io
import xarray as xr

from ..aqd import aqdutils
from ..core import utils


def matlab2datetime(matlab_datenum):
    day = dt.datetime.fromordinal(int(matlab_datenum))
    dayfrac = dt.timedelta(days=matlab_datenum % 1) - dt.timedelta(days=366)
    return day + dayfrac


def load_mat_file(filnam):
    mat = utils.loadmat(filnam)
    bindist = (
        mat["Config"]["Burst_BlankingDistance"]
        + mat["Config"]["Burst_CellSize"] / 2
        + mat["Config"]["Burst_CellSize"] * np.arange(mat["Config"]["Burst_NCells"])
    )

    ds_dict = {}  # initialize dictionary for xarray datasets
    if (
        mat["Config"]["Plan_BurstEnabled"] == "True"
        and mat["Config"]["Burst_RawAltimeter"] == 1
    ):
        # BurstRawAltimeter
        dsbra = xr.Dataset()
        dsbra["time"] = xr.DataArray(
            [matlab2datetime(x) for x in mat["Data"]["BurstRawAltimeter_Time"]],
            dims="time",
        )
        dsbra["time"] = pd.DatetimeIndex(dsbra["time"])
        dsbra["time"] = pd.DatetimeIndex(dsbra["time"])
        dsbra.attrs["data_type"] = "BurstRawAltimeter"
        ds_dict["dsbra"] = dsbra

    if (
        mat["Config"]["Plan_BurstEnabled"] == "True"
        and mat["Config"]["Burst_NBeams"] == 5
    ):
        # IBurst
        dsi = xr.Dataset()
        dsi["time"] = pd.DatetimeIndex(
            xr.DataArray(
                [matlab2datetime(x) for x in mat["Data"]["IBurst_Time"]],
                dims="time",
            )
        )
        dsi["time"] = pd.DatetimeIndex(dsi["time"])
        dsi["bindist"] = xr.DataArray(bindist, dims="bindist")
        dsi.attrs["data_type"] = "IBurst"
        ds_dict["dsi"] = dsi

    if mat["Config"]["Plan_BurstEnabled"] == "True":
        # Burst
        dsb = xr.Dataset()
        dsb["time"] = pd.DatetimeIndex(
            xr.DataArray(
                [matlab2datetime(x) for x in mat["Data"]["Burst_Time"]],
                dims="time",
            )
        )
        dsb["time"] = pd.DatetimeIndex(dsb["time"])
        dsb["bindist"] = xr.DataArray(bindist, dims="bindist")
        dsb.attrs["data_type"] = "Burst"
        ds_dict["dsb"] = dsb

    for k in mat["Data"]:
        if "BurstRawAltimeter" in k:
            if "_Time" not in k:
                if mat["Data"][k].ndim == 1:
                    dsbra[k.split("_")[1]] = xr.DataArray(mat["Data"][k], dims="time")
                elif mat["Data"][k].ndim == 2:
                    # print("still need to process", k, mat["Data"][k].shape)
                    pass
        elif "IBurst" in k:
            if "_Time" not in k:
                if mat["Data"][k].ndim == 1:
                    dsi[k.split("_")[1]] = xr.DataArray(mat["Data"][k], dims="time")
                elif mat["Data"][k].ndim == 2:
                    if "AHRSRotationMatrix" in k:
                        coords = {"dimRM": np.arange(9)}
                        dsi["AHRSRotationMatrix"] = xr.DataArray(
                            mat["Data"][k], dims=["time", "dimRM"]
                        )
                    if "Magnetometer" in k:
                        coords = {"dimM": np.arange(3)}
                        dsi["Magnetometer"] = xr.DataArray(
                            mat["Data"][k], dims=["time", "dimM"]
                        )
                    if "Accelerometer" in k:
                        coords = {"dimA": np.arange(3)}
                        dsi["Accelerometer"] = xr.DataArray(
                            mat["Data"][k], dims=["time", "dimA"]
                        )
                    # only checks to see if cells match on first sample
                    elif mat["Data"][k].shape[1] == mat["Data"]["IBurst_NCells"][0]:
                        dsi[k.split("_")[1]] = xr.DataArray(
                            mat["Data"][k], dims=["time", "bindist"]
                        )
                else:
                    print("still need to process", k, mat["Data"][k].shape)
        elif re.match("^Burst_", k):
            if "_Time" not in k:
                if mat["Data"][k].ndim == 1:
                    dsb[k.split("_")[1]] = xr.DataArray(mat["Data"][k], dims="time")
                elif mat["Data"][k].ndim == 2:
                    if "AHRSRotationMatrix" in k:
                        coords = {"dimRM": np.arange(9)}
                        dsb["AHRSRotationMatrix"] = xr.DataArray(
                            mat["Data"][k], dims=["time", "dimRM"]
                        )
                    if "Magnetometer" in k:
                        coords = {"dimM": np.arange(3)}
                        dsb["Magnetometer"] = xr.DataArray(
                            mat["Data"][k], dims=["time", "dimM"]
                        )
                    if "Accelerometer" in k:
                        coords = {"dimA": np.arange(3)}
                        dsb["Accelerometer"] = xr.DataArray(
                            mat["Data"][k], dims=["time", "dimA"]
                        )
                    # only checks to see if cells match on first sample
                    elif mat["Data"][k].shape[1] == mat["Data"]["Burst_NCells"][0]:
                        dsb[k.split("_")[1]] = xr.DataArray(
                            mat["Data"][k], dims=["time", "bindist"]
                        )
                else:
                    print("still need to process", k, mat["Data"][k].shape)
        else:
            print("missing variable:", k)

    for ds in ds_dict:
        read_config_mat(mat, ds_dict[ds])

    for ds in ds_dict:
        add_descriptions(mat, ds_dict[ds])

    for ds in ds_dict:
        add_units(mat, ds_dict[ds])
        add_transmatrix(mat, ds_dict[ds])

    return ds_dict


def read_config_mat(mat, ds):
    for k in mat["Config"]:
        if k == "Burst_Beam2xyz":
            ds.attrs[f"SIG{k}"] = str(mat["Config"][k])
        else:
            ds.attrs[f"SIG{k}"] = mat["Config"][k]


def add_descriptions(mat, ds):
    for k in mat["Descriptions"]:
        var = k.split("_")[1]
        if var in ds:
            if "long_name" not in ds[var].attrs:
                ds[var].attrs["long_name"] = mat["Descriptions"][k]
            # else:
            #     warnings.warn(
            #         f"long_name already exists for {ds.attrs['data_type']} {var} {k}"
            #     )


def add_units(mat, ds):
    for k in mat["Units"]:
        var = k.split("_")[1]
        if var in ds:
            if "units" not in ds[var].attrs:
                ds[var].attrs["units"] = mat["Units"][k]
            # else:
            #     warnings.warn(
            #         f"units already exists for {ds.attrs['data_type']} {var} {k}"
            #     )


def add_transmatrix(mat, ds):
    for k in mat["Config"]:
        if "Beam2xyz" in k:
            var = k.split("_")[1]
            ds[var] = xr.DataArray(mat["Config"][k])


def mat_to_cdf(metadata):
    """warnings.warn(
        "The use of mat_to_cdf is deprecated. Use raw_to_cdf instead. Refer to the stglib documentation for more details.",
        DeprecationWarning,
        stacklevel=2,
    )
    """
    tic = time.time()
    basefile = metadata["basefile"]

    if "prefix" in metadata:
        prefix = metadata["prefix"]
    else:
        prefix = ""
    basefile = prefix + basefile

    if "outdir" in metadata:
        outdir = metadata["outdir"]
    else:
        outdir = ""

    utils.check_valid_globalatts_metadata(metadata)
    aqdutils.check_valid_config_metadata(metadata)

    # read in mat files in proper order
    nn = []
    for f in glob.glob(f"{basefile}_*.mat"):
        n = int(f.split("_")[-1].split(".mat")[0])
        nn.append(n)
    nn = np.array(nn)
    nn.sort()
    for k in nn:
        f = f"{basefile}_{k}.mat"
        print(f)
        dsd = load_mat_file(f)
        filstub = f.split("/")[-1].split(".mat")[0]
        num = filstub.split("_")[-1]

        for dsn in dsd:
            ds = dsd[dsn]
            ds = utils.write_metadata(ds, metadata)
            ds = utils.ensure_cf(ds)
            cdf_filename = (
                outdir
                + prefix
                + ds.attrs["filename"]
                + "-"
                + ds.attrs["data_type"]
                + "-"
                + num
                + "-raw.cdf"
            )
            ds.to_netcdf(cdf_filename)
            print(f"Finished writing data to {cdf_filename}")

    # read in Burst -raw.cdf and make one combined per data_type
    if "dsb" in dsd:
        fin = outdir + "*-Burst-*.cdf"
        ds = xr.open_mfdataset(fin, parallel=True)
        ds = aqdutils.check_attrs(ds, inst_type="SIG")
        if "Beam2xyz" in ds:
            ds["Beam2xyz"] = ds["Beam2xyz"].isel(time=0, drop=True)
        # write out all into single -raw.cdf files per data_type
        cdf_filename = prefix + ds.attrs["filename"] + "_burst-raw.cdf"
        print("writing Burst to netcdf")
        ds.to_netcdf(cdf_filename)
        print(f"Finished writing data to {cdf_filename}")

    if "dsi" in dsd:
        fin = outdir + "*-IBurst-*.cdf"
        ds = xr.open_mfdataset(fin, parallel=True)
        ds = aqdutils.check_attrs(ds, inst_type="SIG")
        if "Beam2xyz" in ds:
            ds["Beam2xyz"] = ds["Beam2xyz"].isel(time=0, drop=True)
        # write out all into single -raw.cdf files per data_type
        cdf_filename = prefix + ds.attrs["filename"] + "_iburst-raw.cdf"
        print("writing IBurst to netcdf")
        ds.to_netcdf(cdf_filename)
        print(f"Finished writing data to {cdf_filename}")

    if "dsbra" in dsd:
        fin = outdir + "*-BurstRawAltimeter-*.cdf"
        ds = xr.open_mfdataset(fin, parallel=True)
        ds = aqdutils.check_attrs(ds, inst_type="SIG")
        # write out all into single -raw.cdf files per data_type
        cdf_filename = prefix + ds.attrs["filename"] + "_burstrawalt-raw.cdf"
        print("writing BurstRawAltimeter to netcdf")
        ds.to_netcdf(cdf_filename)
        print(f"Finished writing data to {cdf_filename}")

    toc = time.time()
    etime = round(toc - tic, 0)
    print(f"elapsed time = {etime}")