#!/usr/bin/env python3

import sys
import logging
import math
import wave
import numpy as np

logger = logging.getLogger(__name__)

def voice_modulate(wav_filename: str, config: dict, transmit_function=None):
    """
    Perform Narrowband FM modulation on a WAV file and transmit or save the I/Q samples.

    :param wav_filename: Path to the input WAV file.
    :param config: Configuration dictionary with keys:
        - 'sample_rate': Desired modulation sample rate (Hz).
        - 'freq_deviation': Frequency deviation for FM (Hz).
        - 'output': 'hackrf', 'file:<path>', or 'stdout'.
        - 'format': 'f32' or 's8'.
    :param transmit_function: Optional function to transmit I/Q samples (from main.py).
    """
    # Extract config parameters
    sr_mod = int(config.get('sample_rate', 240000))     # e.g., 240 kHz
    freq_dev = float(config.get('freq_deviation', 5000.0))
    out_target = config.get('output', 'stdout').lower()
    out_format = config.get('format', 'f32').lower()

    # Read WAV file
    try:
        with wave.open(wav_filename, 'rb') as wf:
            channels = wf.getnchannels()
            sample_rate_in = wf.getframerate()
            sampwidth = wf.getsampwidth()
            nframes = wf.getnframes()
            raw_data = wf.readframes(nframes)
    except Exception as e:
        logger.error(f"[Voice] Cannot open WAV file '{wav_filename}': {e}")
        sys.exit(1)

    # Convert PCM to float32
    if sampwidth == 2:
        dtype = np.int16
    elif sampwidth == 4:
        dtype = np.int32
    else:
        logger.error("[Voice] Unsupported WAV bit depth (only 16 or 32 bit).")
        sys.exit(1)

    audio_data = np.frombuffer(raw_data, dtype=dtype)

    # If stereo, take the first channel
    if channels > 1:
        audio_data = audio_data.reshape((-1, channels))
        audio_data = audio_data[:, 0]

    # Normalize to [-1, 1]
    audio_data = audio_data.astype(np.float32) / np.iinfo(dtype).max

    # Resample if needed
    if sample_rate_in != sr_mod:
        logger.info(f"[Voice] Resampling from {sample_rate_in} Hz to {sr_mod} Hz ...")
        factor = sr_mod / sample_rate_in
        new_len = int(len(audio_data) * factor)
        audio_data = np.interp(
            np.linspace(0, len(audio_data), new_len, endpoint=False),
            np.arange(len(audio_data)),
            audio_data
        ).astype(np.float32)

    # Perform Narrowband FM
    phase = 0.0
    fm_samples = []
    for sample in audio_data:
        # Limit sample to [-1, 1]
        sample = max(-1.0, min(1.0, sample))
        freq = freq_dev * sample  # Frequency deviation based on sample
        phase += 2.0 * math.pi * freq / sr_mod
        re = math.cos(phase)
        im = math.sin(phase)
        fm_samples.append(complex(re, im))

    fm_samples = np.array(fm_samples, dtype=np.complex64)

    # Output Handling
    if out_target == 'hackrf':
        if transmit_function is None:
            logger.error("[Voice] Transmit function not provided for HackRF output.")
            sys.exit(1)
        transmit_function(fm_samples, config)
    else:
        # Prepare output
        if out_format not in ["f32", "s8"]:
            logger.warning(f"[Voice] Unsupported output format '{out_format}', defaulting to 'f32'")
            out_format = "f32"

        if out_target.startswith('file:'):
            filepath = out_target[5:]
            try:
                fout = open(filepath, "wb")
                logger.info(f"[Voice] Writing I/Q samples to file '{filepath}'.")
            except IOError:
                logger.error(f"[Voice] Cannot open file '{filepath}' for writing.")
                sys.exit(1)
        else:
            fout = sys.stdout.buffer
            logger.info("[Voice] Writing I/Q samples to stdout.")

        # Interleave I and Q
        interleaved = np.empty(fm_samples.size * 2, dtype=np.float32)
        interleaved[0::2] = np.real(fm_samples)
        interleaved[1::2] = np.imag(fm_samples)

        if out_format == "s8":
            scaled = np.round(interleaved * 127).astype(np.int8)
            fout.write(scaled.tobytes())
        else:
            # 'f32' format
            fout.write(interleaved.tobytes())

        if fout is not sys.stdout.buffer:
            fout.close()
        logger.info("[Voice] FM modulation complete.")
