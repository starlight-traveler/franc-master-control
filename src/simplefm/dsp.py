#!/usr/bin/env python3
import sys
import math
import numpy as np
import logging

# We'll assume the same logger is used across modules
logger = logging.getLogger(__name__)

# If you have a separate transmit function for HackRF in main, you can import it:
# from main import transmit_hackrf
# But that can cause circular imports. Instead, you might pass transmit_hackrf as a callback.

def string_to_audio_data(text: str, sample_rate=8000, tone_freq=800, char_duration=0.2, volume=0.5):
    """
    Convert a string into a simple beep waveform, returning float32 samples in [-1,1].
    Each character is 'beeped' for char_duration seconds, followed by a gap (25% of char_duration).
    """
    char_gap = char_duration * 0.25
    beep_len = int(sample_rate * char_duration)
    gap_len = int(sample_rate * char_gap)

    audio_array = []
    for char in text:
        # beep for beep_len samples
        for i in range(beep_len):
            t = i / float(sample_rate)
            sample_val = volume * math.sin(2.0 * math.pi * tone_freq * t)
            audio_array.append(sample_val)
        # add silence
        audio_array.extend([0.0] * gap_len)

    return np.array(audio_array, dtype=np.float32)

def voice_fm_encode(
    data: str,
    config: dict,
    transmit_function=None
):
    """
    Synthesize beep audio from 'data' (string), FM-modulate it, 
    and either transmit (if transmit_function is provided or output='hackrf') 
    or write to output.

    :param data: The string to synthesize into beeps
    :param config: Configuration dictionary
    :param transmit_function: Optional transmit callback (e.g., transmit_hackrf).
                             If you want to keep the HackRF logic out of this file,
                             pass it in as a function reference. If None, we check
                             if output='hackrf' and can import it ourselves.
    """
    sr_mod = int(config.get('sample_rate', 240000))  # e.g. 240 kHz
    freq_dev = float(config.get('freq_deviation', 5000.0))
    out_target = config.get('output', 'stdout').lower()
    out_format = config.get('format', 'f32').lower()

    # Synthesize audio from string
    sample_rate_for_audio = 8000
    tone_freq = 800
    char_duration = 0.2
    volume = 0.5
    audio_data = string_to_audio_data(
        text=data,
        sample_rate=sample_rate_for_audio,
        tone_freq=tone_freq,
        char_duration=char_duration,
        volume=volume
    )

    # Resample to sr_mod if needed
    if sample_rate_for_audio != sr_mod:
        factor = sr_mod / sample_rate_for_audio
        new_len = int(len(audio_data) * factor)
        audio_data = np.interp(
            np.linspace(0, len(audio_data), new_len, endpoint=False),
            np.arange(len(audio_data)),
            audio_data
        ).astype(np.float32)

    # Simple narrowband FM
    phase = 0.0
    fm_samples = []
    for sample in audio_data:
        freq = freq_dev * sample  # sample in [-1..1]
        phase += 2.0 * math.pi * freq / sr_mod
        re = math.cos(phase)
        im = math.sin(phase)
        fm_samples.append(complex(re, im))

    fm_samples = np.array(fm_samples, dtype=np.complex64)

    # If output is hackrf, transmit
    if out_target == 'hackrf':
        if transmit_function is None:
            # If user didn't pass in a function, we can attempt local import
            from main import transmit_hackrf  # <- depends on your structure
            transmit_hackrf(fm_samples, config)
        else:
            transmit_function(fm_samples, config)
    else:
        # Otherwise write to a file or stdout
        if out_format not in ["f32", "s8"]:
            logger.warning(f"[FM] Unsupported output format '{out_format}', defaulting to 'f32'")
            out_format = "f32"

        if out_target.startswith('file:'):
            filepath = out_target[5:]
            try:
                fout = open(filepath, "wb")
            except IOError:
                logger.error(f"[FM] Error creating output file '{filepath}'")
                sys.exit(1)
        else:
            fout = sys.stdout.buffer

        # Interleave I/Q
        interleaved = np.empty(fm_samples.size * 2, dtype=np.float32)
        interleaved[0::2] = np.real(fm_samples)
        interleaved[1::2] = np.imag(fm_samples)

        if out_format == "s8":
            scaled = np.round(interleaved * 127).astype(np.int8)
            fout.write(scaled.tobytes())
        else:
            # default float32
            fout.write(interleaved.tobytes())

        if fout is not sys.stdout.buffer:
            fout.close()
        logger.info("[FM] Voice FM modulation complete.")
