#!/usr/bin/env python3

import sys
import configparser
import logging
from pathlib import Path
import numpy as np
import subprocess

logger = logging.getLogger(__name__)

'''
##################
General Imports
##################
'''

# Import transmission function to HackRF
from src.transmission import transmit_hackrf

# GFSK
from src.gfsk.dsp import gfsk_modulate, modulate as gfsk_modulate_func

# SimpleFM
from src.simplefm.dsp import voice_fm_encode

# Voice
from src.voice.dsp import voice_modulate
from src.voice.tts import text_to_speech
from src.qpsk.dsp import qpsk_modulator

'''
##################
Modulators
##################
'''

def gfsk_modulator(data: str, config: dict):
    """
    Handle GFSK modulation based on provided data and configuration.
    """
    # Parse bitstream
    bitstream = parse_bitstream(data)

    if config.get('debug', False):
        logger.debug(f"[GFSK] Bitstream length: {len(bitstream)} bits")

    # Perform GFSK modulation
    iq_samples = gfsk_modulate(
        bitstream=bitstream,
        baud_rate=int(config.get('baud_rate', 1200)),
        sample_rate=int(config.get('sample_rate', 48000)),
        freq_deviation=float(config.get('freq_deviation', 750.0)),
        bt=float(config.get('bt', 0.3))
    )

    # Convert list -> np.array for convenience
    iq_samples = np.array(iq_samples, dtype=np.complex64)

    if config.get('output').lower() == 'hackrf':
        # Transmit via HackRF (PyHackRF)
        transmit_hackrf(iq_samples, config)
    else:
        # Determine output format
        iq_sf = config.get('format', 'f32').lower()
        if iq_sf == "s8":
            out_fmt = "IQ_S8"
        elif iq_sf == "f32":
            out_fmt = "IQ_F32"
        elif iq_sf == "pcm":
            out_fmt = "PCM"
        else:
            logger.error(f"[GFSK] Incorrect sample format: {config.get('format')}")
            sys.exit(1)

        # Determine output destination
        output = config.get('output')
        fout = None
        if output and not output.lower().startswith('file:') and output.lower() != 'stdout':
            logger.error("[GFSK] Invalid output option. Use 'stdout', 'file:<filepath>', or 'hackrf'.")
            sys.exit(1)
        elif output.lower().startswith('file:'):
            filepath = output[5:]
            try:
                fout = open(filepath, "wb")
                logger.debug(f"[GFSK] Writing output to file '{filepath}'")
            except IOError:
                logger.error(f"[GFSK] Error creating output file '{filepath}'")
                sys.exit(1)
        else:
            # Default to stdout as binary
            fout = sys.stdout.buffer
            logger.debug(f"[GFSK] Writing output to stdout")

        # Write I/Q samples
        gfsk_modulate_func(iq_samples, out_fmt, fout)

        if fout and fout is not sys.stdout.buffer:
            fout.close()

        if config.get('debug', False):
            logger.info(f"[GFSK] Modulation complete. Output written to '{output if output else 'stdout'}'.")

def aprs_encode(message: str, config: dict):
    """
    1) Spawns the `aprs` tool to encode the message into an AX.25/APRS waveform.
    2) Captures the output in the specified format (default 'f32' or 's8').
    3) If output == 'hackrf', transmit via HackRF; else write to file or stdout.

    Expected config dictionary keys:
      'callsign'     -> str, default 'NOCALL'
      'destination'  -> str, default 'APRS'
      'path'         -> str, e.g. 'WIDE1-1,WIDE2-1'
      'format'       -> str, e.g. 'f32', 's8', 'pcm'
      'output'       -> str, e.g. 'hackrf', 'stdout', or a filename
      'debug'        -> bool
      (HackRF-related if output == 'hackrf')
        'frequency', 'sample_rate', 'txvga_gain', 'txamp_enable'

    :param message: APRS message payload (string).
    :param config: Dictionary with APRS/HackRF config.
    """
    callsign    = config.get('callsign', 'NOCALL')
    destination = config.get('destination', 'APRS')
    path        = config.get('path', 'WIDE1-1,WIDE2-1')
    out_format  = config.get('format', 'f32')  # e.g. 'f32', 's8', 'pcm'
    output      = config.get('output', 'stdout')
    debug       = bool(config.get('debug', False))

    # Build the command
    cmd = [
        "/local/franc/franc-master-control/src/aprs/aprs-sdr-build/bin/aprs-sdr",
        "-c", callsign,
        "-d", destination,
        "-p", path,
        "-f", out_format,
        "Hello APRS"
    ]

    if debug:
        cmd.append("-v")
        logger.debug(f"APRS command: {' '.join(cmd)}")

    # Spawn the 'aprs' process capturing its stdout
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )
    except FileNotFoundError:
        logger.error("Could not find 'aprs-sdr' executable in PATH.")
        return
    except Exception as exc:
        logger.error(f"Error spawning 'aprs': {exc}")
        return

    out_bytes, err_bytes = proc.communicate()
    retcode = proc.returncode

    if debug and err_bytes:
        logger.debug(f"aprs STDERR:\n{err_bytes.decode(errors='replace')}")

    if retcode != 0:
        logger.error(f"'aprs' returned non-zero exit code: {retcode}")
        logger.error(f"STDERR:\n{err_bytes.decode(errors='replace')}")
        return

    if len(out_bytes) == 0:
        logger.error("No output received from aprs tool.")
        return

    logger.info(f"Received {len(out_bytes)} bytes from 'aprs'.")

    ############################
    # If the user asked for raw I/Q data (like s8 or f32)
    # we handle it. If it's PCM, you might handle differently.
    ############################
    if out_format == 's8':
        # Interpreted as signed 8-bit I/Q interleaved
        samples_int8 = np.frombuffer(out_bytes, dtype=np.int8)
        if len(samples_int8) % 2 != 0:
            logger.warning("Captured s8 data has an odd length -> possible misalignment.")

        # Reshape to [N,2] -> complex
        samples_2col = samples_int8.reshape((-1, 2))
        i_samples = samples_2col[:, 0].astype(np.float32)
        q_samples = samples_2col[:, 1].astype(np.float32)
        complex_samples = i_samples + 1j * q_samples

        # Normalize to [-1,1]
        peak = np.max(np.abs(complex_samples))
        if peak > 0:
            complex_samples /= peak
        iq_data = complex_samples.astype(np.complex64)

    elif out_format == 'f32':
        # Interpreted as float32 I/Q interleaved
        samples_f32 = np.frombuffer(out_bytes, dtype=np.float32)
        if len(samples_f32) % 2 != 0:
            logger.warning("Captured f32 data has an odd length -> possible misalignment.")

        samples_2col = samples_f32.reshape((-1, 2))
        i_samples = samples_2col[:, 0]
        q_samples = samples_2col[:, 1]
        iq_data = i_samples + 1j * q_samples

    elif out_format == 'pcm':
        # Could be raw audio PCM?  
        # For example, 16-bit signed mono. Implementation can vary—this is just a placeholder:
        iq_data = None  # If you need to handle PCM for HackRF, you'd do your own steps here.
    else:
        logger.warning(f"Unknown or unhandled format '{out_format}'.")
        iq_data = None

    ####################################
    # Output / Transmit
    ####################################
    if output.lower() == 'hackrf':
        if iq_data is None:
            logger.error("No valid I/Q data to transmit (check your format?).")
            return
        # Transmit via HackRF
        logger.info("Transmitting APRS waveform via HackRF...")
        transmit_hackrf(iq_data, config)
    elif output.lower() == 'stdout':
        # Write raw bytes to stdout
        sys.stdout.buffer.write(out_bytes)
        logger.info("[APRS] Wrote raw data to stdout.")
    else:
        # Output to file
        try:
            with open(output, 'wb') as f:
                f.write(out_bytes)
            logger.info(f"[APRS] Wrote {len(out_bytes)} bytes to file: {output}")
        except Exception as e:
            logger.error(f"Error writing APRS data to '{output}': {e}")


'''
##################
Bit Stream
##################
'''

def parse_bitstream(input_source: str) -> list:
    """
    Parse the input bitstream from a string or file.
    input_source: 'str:<bitstring>' or 'file:<filepath>'
    Returns a list of booleans representing the bitstream.
    """
    if input_source.startswith("str:"):
        bitstr = input_source[4:]
        return [c == '1' for c in bitstr if c in ['0', '1']]
    elif input_source.startswith("file:"):
        filepath = input_source[5:]
        try:
            with open(filepath, 'r') as f:
                bitstr = f.read().strip()
                return [c == '1' for c in bitstr if c in ['0', '1']]
        except IOError:
            logger.error(f"[GFSK] Error reading bitstream file '{filepath}'")
            sys.exit(1)
    else:
        logger.error("[GFSK] Invalid input source. Use 'str:<bits>' or 'file:<filepath>'")
        sys.exit(1)

