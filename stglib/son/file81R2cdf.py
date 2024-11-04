import os
from math import nan

import numpy as np
import pandas as pd
import xarray as xr

from . import sonutils
from .core import utils


def read_81R(fname):
    # Parse an 81R file returned from an 881A-GS model imagenex sonar
    # Input:
    #    fname: The name of the .81R file being processed
    # Outputs:
    #    FanData: A dictionary containing the entire file as a numpy array of bytes
    #        as well as the portion of the file that contains the sonar return data
    #    FanHeader: A dictionary containing relevant information for processing the
    #        sonar data that has been extracted from the various headers
    #    FanSwitches: A dictionary containg the information extracted from the
    #        universal file header

    # Open and read the file in a binary format
    fid = open(fname, "rb")
    data = fid.read()

    # Universal lengths of the file header and the device list
    PINGHEADERBYTES = 1024
    DEVICELISTBYTES = 1024

    # Parse the start of the file
    time, header = sonutils.parse_pingHeader(data[:PINGHEADERBYTES], fname[-12:-8])

    # Gather the size of the switch commands and the return data header
    switchCommandBytes = header["SwitchCommandBytes"]
    returnHeaderBytes = header["ReturnHeaderBytes"]

    # Drop unneeded variables
    del header["SwitchCommandBytes"]
    del header["ReturnHeaderBytes"]
    del header["ReturnDataHeaderType"]

    # Extract information from the first set of switch commands
    offset = PINGHEADERBYTES + DEVICELISTBYTES
    SwitchSettings = sonutils.parse_switchCommand(
        data[offset : offset + switchCommandBytes]
    )

    # Add switch settings to header info
    header.update(SwitchSettings)

    # Calculate the number of pings using the file size and the size of each ping
    npings = int(os.path.getsize(fname) / header["TotalBytes"])

    # Convert the binary file into a 2-d numpy array
    imagedata = np.array(bytearray(data)).reshape(npings, header["TotalBytes"])

    # Initialize the dictionary
    variables = {}

    # Initialize variables to make the loop more efficient
    variables["ReturnDataHeaderType"] = [""] * npings
    # variables["HeadID"] = [""] * npings
    variables["HeadPosition"] = [nan] * npings
    variables["HeadAngle"] = [nan] * npings
    variables["StepDirection"] = [nan] * npings
    # variables["Range"] = [0] * npings
    variables["ProfileRange"] = [nan] * npings
    variables["NDataBytes"] = [nan] * npings
    variables["SonarPosition"] = [nan] * npings
    variables["SonarAngle"] = [nan] * npings
    variables["Pitch"] = [nan] * npings
    variables["Roll"] = [nan] * npings
    variables["Heading"] = [nan] * npings
    variables["NReturnBytes"] = [nan] * npings
    variables["GyroHeading"] = [nan] * npings

    # Extract data from each ping
    for i in range(npings):
        # Gather data from the universal header
        time, PingHeader = sonutils.parse_pingHeader(
            imagedata[i, :PINGHEADERBYTES].tobytes(), fname[-12:-8]
        )

        # Gather data from the switch commands
        offset = PINGHEADERBYTES + DEVICELISTBYTES
        SwitchCommand = sonutils.parse_switchCommand(
            imagedata[i, offset : offset + switchCommandBytes].tobytes()
        )

        # Gather data from the return data header
        offset += switchCommandBytes
        ReturnHeader = sonutils.parse_returnHeader(
            imagedata[i, offset : offset + returnHeaderBytes].tobytes(), SwitchCommand
        )

        # If the header isn't empty, transfer the gathered data into the output dictionary
        if ReturnHeader:
            variables["ReturnDataHeaderType"][i] = ReturnHeader["ReturnDataHeaderType"]
            # variables["HeadID"][i] = ReturnHeader["HeadID"]
            variables["HeadPosition"][i] = ReturnHeader["HeadPosition"]
            variables["HeadAngle"][i] = ReturnHeader["HeadAngle"]
            variables["StepDirection"][i] = ReturnHeader["StepDirection"]
            # variables["Range"][i] = ReturnHeader["Range"]
            variables["ProfileRange"][i] = ReturnHeader["ProfileRange"]
            variables["NDataBytes"][i] = ReturnHeader["NDataBytes"]
            variables["SonarPosition"][i] = ReturnHeader["SonarPosition"]
            variables["SonarAngle"][i] = ReturnHeader["SonarAngle"]
            variables["Pitch"][i] = ReturnHeader["Pitch"]
            variables["Roll"][i] = ReturnHeader["Roll"]
            variables["Heading"][i] = ReturnHeader["Heading"]
            variables["GyroHeading"][i] = ReturnHeader["GyroHeading"]
            # variables["time"] = time
            # variables['StartGain'][i] = SwitchCommand['StartGain']
            if "NReturnBytes" in ReturnHeader:
                variables["NReturnBytes"][i] = ReturnHeader["NReturnBytes"]
            else:
                variables["NReturnBytes"][i] = float("NaN")
                print(f"Problem at ping {i}")

    # Isolate the section of the numpy array that corresponds to the return data
    offset = PINGHEADERBYTES + DEVICELISTBYTES + switchCommandBytes + returnHeaderBytes
    image = imagedata[:, offset:-1]

    # Convert to xarray
    header.update({"ReturnDataHeaderType": variables["ReturnDataHeaderType"][0]})
    del variables["ReturnDataHeaderType"]
    del variables["NDataBytes"]
    del variables["NReturnBytes"]

    df = pd.DataFrame.from_dict(variables)
    df.index.names = ["scan"]
    ds = df.to_xarray()

    # # Make xarray with time and echo data
    ds["points"] = range(0, image.shape[1])
    echo_data = xr.DataArray(image, dims=["scan", "points"], name="imagedata")
    ds = xr.merge([ds, echo_data])

    return ds, header, time


# Make raw CDF
def file81R_to_cdf(metadata):

    folder = metadata["folder"]

    # List all files in the current directory
    files = os.listdir(folder)
    names = [file[:-6] for file in files]

    # Find unique names for sets of sweeps
    unique_list = list(set(names))
    unique_list.sort()

    date = []
    # For each sequence (5m or 20m)
    for k in range(0, len(unique_list)):

        # Find sets of sweeps
        sweep_list = [s for s in files if unique_list[k] in s]

        # Read each sweep in set
        for j in range(0, len(sweep_list)):
            if j == 0:
                ds_4sweeps, header, first_time = read_81R(folder + sweep_list[j])
            else:
                ds_new = read_81R(folder + sweep_list[j])[0]
                ds_4sweeps = xr.concat([ds_4sweeps, ds_new], dim="sweep")
        date.append(first_time)

        # Read each set of 4 sweeps
        if k == 0:
            ds = ds_4sweeps
        else:
            ds = xr.concat([ds, ds_4sweeps], dim="time")

    # Add coordinates for sweep and time
    ds = ds.assign_coords(sweep=("sweep", range(0, 4)))
    ds = ds.assign_coords(time=("time", date))

    # Sort header alphabetically and add to global attributes
    header = sorted(header.items())
    ds.attrs = header

    # Reorder dimensions
    ds = ds.transpose("sweep", "time", "points", "scan")

    ds = utils.write_metadata(ds, metadata)

    ds = utils.ensure_cf(ds)

    # configure file
    cdf_filename = ds.attrs["filename"] + "-raw.cdf"

    ds.to_netcdf(cdf_filename, unlimited_dims=["time"])

    print("Finished writing data to %s" % cdf_filename)

    return ds
