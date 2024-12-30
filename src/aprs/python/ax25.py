#!/usr/bin/env python3
import sys
import string

def encode_callsign(callsign: str):
    """
    Encodes a callsign (including possible '-SSID') into a 7-byte array,
    where the SSID is the last nibble.
    """
    cs = callsign.upper()
    if len(cs) >= 16:
        sys.stderr.write(f"Invalid callsign: {callsign}\n")
        sys.exit(1)

    # Find '-SSID'
    ssid = 0
    if '-' in cs:
        parts = cs.split('-', 1)
        cs = parts[0]
        try:
            ssid = int(parts[1])
        except ValueError:
            sys.stderr.write(f"Invalid SSID: {parts[1]}\n")
            sys.exit(1)

    if len(cs) > 6:
        sys.stderr.write(f"Invalid callsign: {callsign}\n")
        sys.exit(1)

    if ssid < 0 or ssid > 15:
        sys.stderr.write(f"Invalid ssid: {ssid}\n")
        sys.exit(1)

    # Pad callsign with spaces to 6 chars
    cs = f"{cs:6}"[:6]
    buf = cs + str(ssid)  # 7 chars total
    # Convert to a list of integers
    return [ord(c) for c in buf]

def encode_address(callsign: str, dest: str, path: str):
    """
    Combines destination, source, and digipeaters (path) into one address field.
    Then shifts bits accordingly per AX.25 spec.
    """
    encoded_dest = encode_callsign(dest)
    encoded_callsign = encode_callsign(callsign)

    addr = encoded_dest + encoded_callsign

    # Path can contain multiple digipeaters
    digi_list = path.split(',')
    for digi in digi_list:
        if digi.strip():
            encoded_digi = encode_callsign(digi.strip())
            addr += encoded_digi

    # Shift each address byte left by 1
    result = []
    for b in addr:
        result.append(b << 1)

    # The last byte: set the LSB to 1
    result[-1] |= 0x01
    return result

def calc_fcs(data: list):
    """
    Computes the 16-bit CRC (CRC-CCITT) used in AX.25.
    """
    ret = 0xffff
    for b in data:
        for _ in range(8):
            b1 = (b & 1) != 0
            b2 = (ret & 1) != 0
            ret >>= 1
            if b1 != b2:
                ret ^= 0x8408
            b >>= 1
    return (~ret) & 0xffff

def bit_stuffing(data: list):
    """
    Convert the byte stream into a bit stream with bit stuffing.
    Every 5 consecutive '1' bits gets followed by a '0' bit.
    Returns a list of booleans.
    """
    result = []
    count = 0
    for b in data:
        for _ in range(8):
            bit = (b & 1) != 0
            if bit:
                result.append(True)
                count += 1
                if count == 5:
                    # Stuff a zero
                    result.append(False)
                    count = 0
            else:
                result.append(False)
                count = 0
            b >>= 1
    return result

def nrzi(data: list):
    """
    NRZI encoding:
        0 -> change in tone
        1 -> no change in tone
    data is a list of booleans.
    """
    result = []
    current = True
    for bit in data:
        if not bit:
            current = not current
        result.append(current)
    return result

def ax25frame(callsign: str, dest: str, path: str, info: str, debug: bool):
    """
    Build the full AX.25 frame (with bit stuffing, FCS, flags, etc.)
    Returns a list of booleans representing the entire modulated bit stream.
    """
    control = 0x03
    protocol = 0xf0

    # 1) Encode address
    addr = encode_address(callsign, dest, path)
    frame = addr[:]
    # 2) Control + protocol
    frame.append(control)
    frame.append(protocol)
    # 3) Info bytes
    info_bytes = [ord(c) for c in info]
    frame += info_bytes
    # 4) FCS
    fcs = calc_fcs(frame)
    # FCS is added LSB first
    frame.append(fcs & 0xff)
    frame.append((fcs >> 8) & 0xff)

    stuffed_frame = bit_stuffing(frame)

    result = []
    # 20 zeros for "pre-sync"
    for _ in range(20):
        result.append(False)

    # AX.25 flag = 0x7e = b'01111110', which in LSB is 0,1,1,1,1,1,1,0
    flag = [False, True, True, True, True, True, True, False]

    # Insert multiple flags at the start (like the original code)
    for _ in range(100):
        result.extend(flag)

    # Actual stuffed data
    result.extend(stuffed_frame)
    # Trailing flag
    result.extend(flag)

    if debug:
        sys.stderr.write("Packet: ")
        for b in result:
            sys.stderr.write("1" if b else "0")
        sys.stderr.write("\n")

    return result
