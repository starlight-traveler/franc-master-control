import sys
import subprocess
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)


def spawn_aprs_and_capture(
    message: str,
    callsign: str = "N0CALL",
    destination: str = "APRS",
    path: str = "WIDE1-1,WIDE2-1",
    debug: bool = False,
) -> np.ndarray:
    """
    Spawns the 'aprs' command-line tool, capturing output in s8 format (signed 8-bit I/Q).
    Returns a NumPy array of complex64 samples.
    """

    # Build the aprs command.
    # Use '-f s8' so that the output is in 8-bit signed I/Q form.
    # Adjust if your aprs tool uses a different syntax or defaults.
    cmd = [
        "aprs-sdr",
        "-c", callsign,
        "-d", destination,
        "-p", path,
        "-f", "s8",
    ]

    # Enable verbose debug if requested
    if debug:
        cmd.append("-v")

    # Finally, append the message
    cmd.append(message)

    logger.info(f"Spawning aprs command: {' '.join(cmd)}")

    # Run the 'aprs' program, capturing its stdout as the raw s8 stream.
    # We use subprocess.PIPE so that we can read the bytes directly.
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )
    except FileNotFoundError:
        logger.error("Could not find 'aprs' executable in PATH.")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Error spawning 'aprs': {exc}")
        sys.exit(1)

    # Read the entire output from stdout
    # Note: for large transmissions, you might want to stream this in chunks.
    # For a single short message, reading at once is typically okay.
    out_bytes, err_bytes = proc.communicate()
    retcode = proc.returncode

    if debug and err_bytes:
        logger.debug(f"aprs STDERR:\n{err_bytes.decode(errors='replace')}")

    if retcode != 0:
        logger.error(f"'aprs' returned non-zero exit code: {retcode}")
        logger.error(f"STDERR:\n{err_bytes.decode(errors='replace')}")
        sys.exit(retcode)

    if len(out_bytes) == 0:
        logger.error("No output received from aprs tool.")
        sys.exit(1)

    logger.info(f"Received {len(out_bytes)} bytes of s8 data from aprs.")

    # Interpret the byte stream as signed 8-bit integers:
    samples_int8 = np.frombuffer(out_bytes, dtype=np.int8)

    # The aprs tool's "s8" format is typically interleaved I/Q => [I0, Q0, I1, Q1, ...].
    # We'll convert that to a complex64 array: c[i] = I[i] + jQ[i].
    if len(samples_int8) % 2 != 0:
        logger.warning("Captured s8 data has odd number of samples - might be truncated?")

    # Reshape into [N, 2], then convert to complex
    samples_2col = samples_int8.reshape((-1, 2))
    i_samples = samples_2col[:, 0].astype(np.float32)
    q_samples = samples_2col[:, 1].astype(np.float32)

    complex_samples = i_samples + 1j * q_samples

    # Optionally, you might want to normalize to [-1,1]
    # so that downstream stages match typical HackRF usage.
    # However, if your 'aprs' tool already normalizes or you want to preserve
    # relative amplitude, you can skip this. We'll do a quick normalization:
    peak = np.max(np.abs(complex_samples))
    if peak > 0:
        complex_samples /= peak

    # Convert to complex64
    complex_samples = complex_samples.astype(np.complex64)

    return complex_samples
