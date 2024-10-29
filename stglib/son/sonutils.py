import datetime
import struct


def bin2ascii(binString):
    # Read a set of binary ASCII values and return a string
    # Input:
    #    binString: Binary ASCII value(s)
    # Output:
    #    output: String of characters from binString

    # Create an array of characters
    charArray = [chr(x) for x in binString]

    # Convert the array of characters into one string
    output = ""
    for char in charArray:
        output += char

    # Remove ASCII null values (00 in hex) and return the string
    return output.replace("\x00", "")


def parse_pingHeader(fheader, month_day):
    # Read the universal 81R header using the guide provided by the manual
    # Inputs:
    #    fheader: The file header in binary form
    #    timeprefix: a four digit date string in the format of mmdd extracted
    #        from the filename
    # Outputs:
    #    time: The time at the current ping
    #    pingheader: A dictionary containing information extracted from the header

    # Initialize the dictionary
    pingheader = {}

    # First 3 bytes read 81R
    pingheader["ReturnDataHeaderType"] = bin2ascii(fheader[0:3])

    # Get sonar model
    models = ["881L-GS", "881A-GS", "882L", "882A"]
    son_type = fheader[3]
    pingheader["SonarType"] = "Imagenex " + models[son_type]

    # Get file size information based on the model of the sonar
    switch_size = [128, 40]
    pingheader["SwitchCommandBytes"] = switch_size[fheader[3] % 2]
    return_size = [256, 32]
    pingheader["ReturnHeaderBytes"] = return_size[fheader[3] % 2]
    pingheader["TotalBytes"] = struct.unpack("<I", fheader[4:8])[0]

    # Extract information
    tx_orient = ["Down", "Up"]
    orientation = int(bin(fheader[319])[2:].zfill(8)[7])  # 1 is up
    pingheader["Orientation"] = tx_orient[orientation]
    modes = ["Sector", "Polar", "Sidescan"]
    pingheader["Mode"] = modes[fheader[324]]
    pingheader["RangeOffset"] = struct.unpack("<f", fheader[325:329])[0]
    pingheader["SoundVelocity"] = struct.unpack("<f", fheader[338:342])[0]
    pingheader["TransmitFrequency"] = struct.unpack("<f", fheader[342:346])[0]
    pingheader["PingRepetitionRate"] = struct.unpack("<f", fheader[346:350])[0]
    pingheader["SamplesPerPing"] = struct.unpack("<L", fheader[353:357])[0]
    # pingheader["AcousticRangeSetting"] = struct.unpack("<f", fheader[369:373])[0]
    pingheader["RangeResolution"] = struct.unpack("<f", fheader[373:377])[0]
    pingheader["PingNumber"] = struct.unpack("<L", fheader[377:381])[0]
    pingheader["SystemFlag"] = struct.unpack("<B", fheader[381:382])[0]
    pingheader["GyroStatus"] = struct.unpack("<B", fheader[382:383])[0]
    pingheader["MountingAngleOffset"] = struct.unpack("<f", fheader[383:387])[0]
    pingheader["LocalLatitude"] = struct.unpack("<f", fheader[387:391])[0]
    pingheader["CompassDeclination"] = struct.unpack("<f", fheader[391:395])[0]

    # Concatenate month/day to
    dstr = month_day + bin2ascii(fheader[14:27])
    fmt = "%m%d%Y%H%M%S.%f"
    time = datetime.datetime.strptime(dstr, fmt)

    return time, pingheader


def parse_switchCommand(scommand):
    # Parse the switch commands unique to the 881A-GS Model
    # Input:
    #    scommand: Switch commands in binary format
    # Output:
    #    SwitchCommand: A dictionary containing information extracted

    # Initialize the dictionary
    SwitchCommand = {}

    # All conversions are found in the manual
    SwitchCommand["HeadID"] = scommand[2]
    SwitchCommand["Range"] = scommand[3]
    SwitchCommand["StartGain"] = scommand[8]
    SwitchCommand["LogF"] = 10 * (scommand[9] + 1)
    SwitchCommand["Absorption"] = scommand[10] / 100
    SwitchCommand["TrainAngle"] = 3 * scommand[11] - 180
    SwitchCommand["SectorWidth"] = 3 * scommand[12]
    SwitchCommand["StepSize"] = 0.3 * scommand[13]
    SwitchCommand["PulseLength"] = 10 * scommand[14]
    SwitchCommand["MinRange"] = scommand[15] / 10
    SwitchCommand["NDataPoints"] = scommand[19] * 10
    SwitchCommand["DataBits"] = scommand[20]
    profile_cmd = ["OFF", "ON"]
    profile = scommand[23]
    SwitchCommand["Profile"] = profile_cmd[profile]
    SwitchCommand["Frequency"] = 175 + scommand[25] * 5

    return SwitchCommand


def parse_returnHeader(sheader, switches):
    # Parse the return data header for the 881A-GS model sonar
    # Inputs:
    #    sheader: The return data header in binary form
    #    switches: A dictionary of switch commands created using parseSwitchCommand()
    # Output:
    #    FanHeader: A dictionary containing data extracted from the return data header

    # Initialize the dictionary
    returnHeader = {}
    # A 3-character string that used to determine the size of the sonar output
    returnHeader["ReturnDataHeaderType"] = bin2ascii(sheader[0:3])

    # ID of the transducer head
    # returnHeader["HeadID"] = hex(sheader[3])

    # Extracted using Doug Wilson's method
    returnHeader["HeadPosition"] = (63 & sheader[6]) * 128 + (127 & sheader[5])
    returnHeader["HeadAngle"] = (returnHeader["HeadPosition"] - 600) * switches[
        "StepSize"
    ]

    # Extract additional information
    # Method for step direction taken from the manual
    returnHeader["StepDirection"] = (sheader[6] & 64) >> 6
    # returnHeader["Range"] = sheader[7]

    # The following variables are all extracted using methods provided by the manual
    # Profile Range
    HB = (sheader[9] & 0x7E) >> 1
    LB = ((sheader[9] & 0x01) << 7) | (sheader[8] & 0x7F)
    returnHeader["ProfileRange"] = (HB << 8) | LB

    # Data Bytes
    HB = (sheader[11] & 0x7E) >> 1
    LB = ((sheader[11] & 0x01) << 7) | (sheader[10] & 0x7F)
    returnHeader["NDataBytes"] = (HB << 8) | LB

    # Sonar Position
    HB = (sheader[13] & 0x7E) >> 1
    LB = ((sheader[13] & 0x01) << 7) | (sheader[12] & 0x7F)
    returnHeader["SonarPosition"] = (HB << 8) | LB
    returnHeader["SonarAngle"] = 0.3 * (returnHeader["SonarPosition"] - 600)

    # Pitch
    HB = (sheader[15] & 0x7E) >> 1
    LB = ((sheader[15] & 0x01) << 7) | (sheader[14] & 0x7F)
    returnHeader["Pitch"] = (
        (((HB << 8) | LB) - 16384 * (int(bin(sheader[15])[-1]))) * 360 / 16384
    )

    # Roll
    HB = (sheader[17] & 0x7E) >> 1
    LB = ((sheader[17] & 0x01) << 7) | (sheader[16] & 0x7F)
    returnHeader["Roll"] = ((HB << 8) | LB) * 360 / 16384

    # Heading
    HB = (sheader[19] & 0x7E) >> 1
    LB = ((sheader[19] & 0x01) << 7) | (sheader[18] & 0x7F)
    returnHeader["Heading"] = ((HB << 8) | LB) * 360 / 16384

    # Gyro Heading
    HB = (sheader[22] & 0x7E) >> 1
    LB = ((sheader[22] & 0x01) << 7) | (sheader[21] & 0x7F)
    returnHeader["GyroHeading"] = ((HB << 8) | LB) * 360 / 16384

    # Use the previously extracted 3-character string and data from SwitchCommand to determine
    # the amount of data points per ping. Table containing this information is in the manual
    if returnHeader["ReturnDataHeaderType"] == "INA":
        if switches["DataBits"] == 4:
            returnHeader["NReturnBytes"] = 128
            returnHeader["NPoints"] = 256
        elif switches["DataBits"] == 8:
            returnHeader["NReturnBytes"] = 252
            returnHeader["NPoints"] = 252
        elif switches["DataBits"] == 16:
            returnHeader["NReturnBytes"] = 500
            returnHeader["NPoints"] = 250
    elif returnHeader["ReturnDataHeaderType"] == "INB":
        if switches["DataBits"] == 4:
            returnHeader["NReturnBytes"] = 252
            returnHeader["NPoints"] = 504
        elif switches["DataBits"] == 8:
            returnHeader["NReturnBytes"] = 500
            returnHeader["NPoints"] = 500
        elif switches["DataBits"] == 16:
            returnHeader["NReturnBytes"] = 500
            returnHeader["NPoints"] = 250
    elif returnHeader["ReturnDataHeaderType"] == "INC":
        returnHeader["NPoints"] = 0
    else:
        print(
            f"{returnHeader['ReturnDataHeaderType']} is not a recognized data header type"
        )

    return returnHeader
