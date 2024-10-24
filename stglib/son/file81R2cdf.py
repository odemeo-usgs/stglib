import os

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
    N81RFILEHEADERBYTES = 1024
    NDEVICELISTBYTES = 1024

    # Parse the start of the file
    header = sonutils.parse_pingHeader(data[:N81RFILEHEADERBYTES], fname[-12:-8])[1]

    # Gather the size of the switch commands and the return data header
    switchCommandBytes = header["SwitchCommandBytes"]
    returnHeaderBytes = header["ReturnHeaderBytes"]

    # Drop unneeded variables
    del header["SwitchCommandBytes"]
    del header["ReturnHeaderBytes"]

    # Extract information from the first set of switch commands
    offset = N81RFILEHEADERBYTES + NDEVICELISTBYTES
    SwitchSettings = sonutils.parse_switchCommand(
        data[offset : offset + switchCommandBytes]
    )

    # Add switch settings and filename to header info
    header.update(SwitchSettings)
    header["FileName"] = fname

    # #Extract information from the first return data header
    # offset += switchCommandBytes
    # ReturnHeader = sonutils.parseFanHeader(data[offset:offset+returnHeaderBytes], header)

    # Calculate the number of pings using the file size and the size of each ping
    npings = int(os.path.getsize(fname) / header["TotalBytes"])

    # Convert the binary file into a 2-d numpy array
    imagedata = np.array(bytearray(data)).reshape(npings, header["TotalBytes"])

    # Initialize the dictionary
    variables = {}

    # Initialize variables to make the loop more efficient
    variables["ReturnDataHeaderType"] = [""] * npings
    variables["HeadID"] = [""] * npings
    variables["HeadPosition"] = [0] * npings
    variables["HeadAngle"] = [0] * npings
    variables["StepDirection"] = [0] * npings
    variables["Range"] = [0] * npings
    variables["ProfileRange"] = [0] * npings
    variables["NDataBytes"] = [0] * npings
    variables["Heading"] = [0] * npings
    variables["Pitch"] = [0] * npings
    variables["Roll"] = [0] * npings
    variables["time"] = [0] * npings
    # variables['StartGain'] = [0]*npings
    variables["NReturnBytes"] = [0] * npings

    # Extract data from each ping
    for i in range(npings):
        # Gather data from the universal header
        time, PingHeader = sonutils.parse_pingHeader(
            imagedata[i, :N81RFILEHEADERBYTES].tobytes(), fname[-12:-8]
        )

        # Gather data from the switch commands
        offset = N81RFILEHEADERBYTES + NDEVICELISTBYTES
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
            variables["HeadID"][i] = ReturnHeader["HeadID"]
            variables["HeadPosition"][i] = ReturnHeader["HeadPosition"]
            variables["HeadAngle"][i] = ReturnHeader["HeadAngle"]
            variables["StepDirection"][i] = ReturnHeader["StepDirection"]
            variables["Range"][i] = ReturnHeader["Range"]
            variables["ProfileRange"][i] = ReturnHeader["ProfileRange"]
            variables["NDataBytes"][i] = ReturnHeader["NDataBytes"]
            variables["Heading"][i] = ReturnHeader["Heading"]
            variables["Pitch"][i] = ReturnHeader["Pitch"]
            variables["Roll"][i] = ReturnHeader["Roll"]
            variables["time"][i] = time
            # variables['StartGain'][i] = SwitchCommand['StartGain']
            if "NReturnBytes" in ReturnHeader:
                variables["NReturnBytes"][i] = ReturnHeader["NReturnBytes"]
            else:
                variables["NReturnBytes"][i] = float("NaN")
                print(f"Problem at ping {i}")

    # Isolate the section of the numpy array that corresponds to the return data
    offset = (
        N81RFILEHEADERBYTES + NDEVICELISTBYTES + switchCommandBytes + returnHeaderBytes
    )
    image = imagedata[:, offset:-1]

    # Convert to xarray
    del variables["HeadID"]
    del variables["ReturnDataHeaderType"]
    del variables["NDataBytes"]
    del variables["NReturnBytes"]

    df = pd.DataFrame.from_dict(variables)
    df.index.names = ["time"]
    ds = df.to_xarray()

    # Make xarray with echo data
    ds["sample"] = range(0, image.shape[1])
    echo_data = xr.DataArray(image, dims=["time", "sample"], name="imagedata")
    ds = xr.merge([ds, echo_data])

    return ds, header


# Make raw CDF
def file81R_to_cdf(metadata):
    basefile = metadata["basefile"]

    ds, header = read_81R(basefile + ".81R")

    # Append header to metadata variable
    metadata.update(header)

    ds = utils.write_metadata(ds, metadata)

    ds = utils.ensure_cf(ds)

    # configure file
    cdf_filename = ds.attrs["filename"] + "-raw.cdf"

    ds.to_netcdf("cdf_filename", unlimited_dims=["time"])

    print("Finished writing data to %s" % cdf_filename)

    return ds
