#!/usr/bin/env python3
import logging
import struct
import math
import cmath
from lib.ringbuffer import Ringbuffer

logger = logging.getLogger(__name__)

BUFSIZE = 204800
AUDIO_SAMPLE_RATE = 48000  # 48k
BAUD_RATE = 1200
MARK_HZ = 1200
SPACE_HZ = 2200

def afsk(data: list) -> list:
    """
    AFSK (Audio Frequency-Shift Keying) generation.
    data is a list of booleans (NRZI data).
    Returns a list of float samples (mono audio).
    """
    wave = []
    # 0.5 sec of silence
    for _ in range(AUDIO_SAMPLE_RATE // 2):
        wave.append(0.0)

    phase = 0.0
    gain = 0.5
    samples_per_bit = AUDIO_SAMPLE_RATE // BAUD_RATE

    for bit in data:
        freq = MARK_HZ if bit else SPACE_HZ
        phase_inc = 2.0 * math.pi * freq / AUDIO_SAMPLE_RATE
        for _ in range(samples_per_bit):
            wave.append(math.sin(phase) * gain)
            phase += phase_inc
            if phase > 2.0 * math.pi:
                phase -= 2.0 * math.pi

    # 0.5 sec of silence
    for _ in range(AUDIO_SAMPLE_RATE // 2):
        wave.append(0.0)

    return wave

def Izero(x: float) -> float:
    """
    Calculate the 0th order Modified Bessel function of the first kind, I0(x).
    Used in Kaiser window design.
    """
    # This is a series expansion approach
    EPSILON = 1.0e-21
    s = 1.0
    d = 1.0
    y = (x / 2.0) ** 2
    n = 1
    while d > EPSILON * s:
        d *= y / n / n
        s += d
        n += 1
    return s

def compute_ntaps(sampling_freq: float, transition_width: float, beta: float) -> int:
    """
    Estimate number of taps for the Kaiser filter.
    """
    # a ~ (beta / 0.1102) + 8.7 in C++ code. They used param=7.0 => beta=7.0
    a = beta / 0.1102 + 8.7
    ntaps = int(a * sampling_freq / (22.0 * transition_width))
    # Force odd number of taps
    if ntaps % 2 == 0:
        ntaps += 1
    return ntaps

def kaiser(ntaps: int, beta: float) -> list:
    """
    Generate a Kaiser window of length ntaps, parameter beta.
    """
    IBeta = 1.0 / Izero(beta)
    inm1 = 1.0 / (ntaps - 1)
    w = [0.0] * ntaps
    for i in range(ntaps):
        val = 2.0 * i * inm1 - 1.0
        # sqrt(1 - val^2)
        tmp = math.sqrt(max(0.0, 1.0 - val * val))
        w[i] = Izero(beta * tmp) * IBeta
    return w

def lowpass(gain: float, sampling_freq: float, cutoff_freq: float, transition_width: float) -> list:
    """
    Create a lowpass FIR filter using Kaiser window design.
    """
    beta = 7.0
    ntaps = compute_ntaps(sampling_freq, transition_width, beta)
    w = kaiser(ntaps, beta)

    M = (ntaps - 1) // 2
    fwT0 = 2.0 * math.pi * cutoff_freq / sampling_freq

    taps = [0.0] * ntaps
    for n in range(-M, M+1):
        idx = n + M
        if n == 0:
            taps[idx] = (fwT0 / math.pi) * w[idx]
        else:
            taps[idx] = (math.sin(n * fwT0) / (n * math.pi)) * w[idx]

    # Normalize so that gain at 0 freq is 'gain'
    fmax = 0.0
    for i in range(ntaps):
        fmax += taps[i]
    # A simpler approach: sum-of-impulse = DC gain
    # The code in the original C++ sums taps differently,
    # but let's do a direct sum for normalization:
    if abs(fmax) < 1e-12:
        fmax = 1.0

    norm_factor = gain / fmax
    for i in range(ntaps):
        taps[i] *= norm_factor

    return taps

def fmmod(input_data: list, sensitivity: float, last_phase: float, output: Ringbuffer):
    """
    FM modulator: output I/Q into the ring buffer.
    `input_data` is a list of floats.
    `sensitivity` is a float (2 * pi * freqDev / sampleRate).
    Returns the updated phase.
    """
    phase = last_phase
    for samp in input_data:
        phase += samp * sensitivity
        while phase > math.pi:
            phase -= 2.0 * math.pi
        while phase <= -math.pi:
            phase += 2.0 * math.pi
        output.insert(complex(math.cos(phase), math.sin(phase)))
    return phase

def naive_interpolate(input_data: list, interpolation: int, taps: list) -> list:
    """
    A naive up-sampling approach, followed by FIR filtering.
    input_data is a list of complex samples.
    """
    # Make taps length multiple of interpolation
    if len(taps) % interpolation != 0:
        pad = interpolation - (len(taps) % interpolation)
        taps = taps + [0.0] * pad

    # Upsample
    tmp = []
    for sample in input_data:
        # (interpolation-1) zeros, then sample
        for _ in range(interpolation - 1):
            tmp.append(0+0j)
        tmp.append(sample)

    taps_count = len(taps)
    output = []
    processed = len(tmp) - taps_count + 1
    if processed < 0:
        processed = 0

    for i in range(processed):
        acc = 0+0j
        for j in range(taps_count):
            acc += tmp[i + j] * taps[taps_count - j - 1]
        output.append(acc)

    return output

class FIRInterpolator:
    """
    Polyphase FIR interpolator.
    """
    def __init__(self, interpolation: int, taps: list):
        # Make sure taps length is multiple of interpolation
        if len(taps) % interpolation != 0:
            pad = interpolation - (len(taps) % interpolation)
            taps += [0.0] * pad

        self.interpolation = interpolation
        self.nfilters = interpolation
        self.ntaps = len(taps) // interpolation

        # Split taps into polyphase filters
        self.xtaps = []
        for i in range(self.nfilters):
            self.xtaps.append([0.0] * self.ntaps)

        for i, val in enumerate(taps):
            self.xtaps[i % self.nfilters][i // self.nfilters] = val

    def interpolate(self, input_buf: Ringbuffer, output_list: list) -> int:
        """
        Read from 'input_buf', produce upsampled data in 'output_list'.
        Returns how many samples from 'input_buf' were consumed.
        """
        input_size = input_buf.readAvailable()
        # We need at least 'ntaps' to process one block
        if input_size < self.ntaps:
            return 0

        processed_count = input_size - self.ntaps + 1
        for i in range(processed_count):
            # For each polyphase filter
            for j in range(self.nfilters):
                acc = 0+0j
                for k in range(self.ntaps):
                    acc += input_buf[i + k] * self.xtaps[j][self.ntaps - k - 1]
                output_list.append(acc)

        return processed_count

def f32_to_s8(input_data: list) -> bytearray:
    """
    Convert float I/Q samples in range [-1, 1] to int8 I/Q pairs.
    """
    import struct
    out = bytearray()
    # clamp function
    def clamp_schar(x):
        if x > 127.0: return 127
        if x < -128.0: return -128
        return int(x)

    for cplx in input_data:
        re = clamp_schar(cplx.real * 127.0)
        im = clamp_schar(cplx.imag * 127.0)
        out += struct.pack('bb', re, im)
    return out

def modulate(waveform: list, iq_format: str) -> list:
    """
    FM modulation + upsampling by 50.
    Returns IQ samples according to the specified iq_format.
    iq_format can be 'IQ_S8', 'IQ_F32', or 'PCM_F32'.
    """
    max_deviation = 5000.0  # 5 kHz deviation
    sensitivity = 2.0 * math.pi * max_deviation / AUDIO_SAMPLE_RATE
    factor = 50.0
    fractional_bw = 0.1
    halfband = 0.5
    trans_width = halfband - fractional_bw
    mid_transition_band = halfband - (trans_width / 2.0)

    logger.debug("=== modulate() start ===")
    logger.debug("Waveform length (input): %d", len(waveform))
    logger.debug("Requested IQ format: %s", iq_format)
    logger.debug("FM sensitivity (rad/sample): %.6f", sensitivity)
    logger.debug("Upsampling factor: %d", int(factor))
    logger.debug("Lowpass filter design: cutoff=%.3f, transition=%.3f", mid_transition_band, trans_width)

    taps = lowpass(factor, AUDIO_SAMPLE_RATE, mid_transition_band, trans_width)
    logger.debug("Number of FIR taps: %d", len(taps))

    mod_buf = Ringbuffer(BUFSIZE * 2)
    interp = FIRInterpolator(int(factor), taps)
    last_phase = 0.0
    offset = 0
    wave_len = len(waveform)
    iq_samples = []

    # Main chunk loop
    while offset < wave_len:
        chunk_end = min(offset + BUFSIZE, wave_len)
        chunk_data = waveform[offset:chunk_end]

        logger.debug("Processing chunk offset=%d..%d (size=%d)", offset, chunk_end, len(chunk_data))
        logger.debug("Current ring buffer available before FM mod: %d", mod_buf.writeAvailable())

        # 1) FM mod -> writes complex samples into `mod_buf`
        last_phase = fmmod(chunk_data, sensitivity, last_phase, mod_buf)

        logger.debug("Current ring buffer after FM mod: readAvail=%d, writeAvail=%d",
                     mod_buf.readAvailable(), mod_buf.writeAvailable())

        # 2) Interpolate from the ring buffer
        interp_buf = []
        processed = interp.interpolate(mod_buf, interp_buf)
        if processed == 0:
            logger.debug("No samples were processed by the interpolator (processed=0). Breaking early.")
            break

        logger.debug("Interpolator output samples: %d  (processed %d from ring buffer)", len(interp_buf), processed)

        # Remove what was processed from ring buffer
        mod_buf.remove(processed)

        # 3) Convert or store samples according to the format
        if iq_format == "IQ_S8":
            samples_s8 = f32_to_s8(interp_buf)
            iq_samples.extend(samples_s8)
            logger.debug("Appending %d S8 bytes to output (IQ pairs). Total so far: %d",
                         len(samples_s8), len(iq_samples))
        elif iq_format == "IQ_F32":
            # Each complex sample => 2 floats
            start_len = len(iq_samples)
            for cplx in interp_buf:
                iq_samples.extend(struct.pack('ff', cplx.real, cplx.imag))
            logger.debug("Appending %d float32 bytes. Total so far: %d",
                         len(iq_samples) - start_len, len(iq_samples))
        else:
            # Real part only -> float32
            start_len = len(iq_samples)
            for cplx in interp_buf:
                iq_samples.extend(struct.pack('f', cplx.real))
            logger.debug("Appending %d float32 bytes (real only). Total so far: %d",
                         len(iq_samples) - start_len, len(iq_samples))

        offset = chunk_end
        logger.debug("Next offset set to %d", offset)

    # Optional final flush for any leftover data in `mod_buf`
    # If you suspect leftover samples remain in the ring buffer, you can do:
    #
    # logger.debug("Flushing remaining data in ring buffer...")
    # while True:
    #     interp_buf = []
    #     processed = interp.interpolate(mod_buf, interp_buf)
    #     if processed == 0:
    #         break
    #     mod_buf.remove(processed)
    #     # Append to iq_samples just as above

    logger.debug("Finished main loop. Total I/Q sample bytes: %d", len(iq_samples))
    logger.debug("=== modulate() end ===")

    return iq_samples


def gen_iq_s8(callsign: str, user_path: str, info: str):
    """
    Equivalent to the C function:
        int8_t* gen_iq_s8(const char *callsign, const char *user_path, const char *info, int32_t *total)
    Returns a bytes object containing modulated IQ in s8 format.

    Note: This is a convenience wrapper in Python.
    """
    from io import BytesIO
    import struct

    dest = "APRS"

    # Construct AX.25 frame
    from ax25 import ax25frame, nrzi
    frame = ax25frame(callsign, dest, user_path, info, False)
    frame_nrzi = nrzi(frame)
    wave = afsk(frame_nrzi)

    # The original C code expects wave.size() * 50 * 2 bytes
    # wave.size() because each sample -> 1 sample => 50 IQ pairs => 50*2 int8
    total_size = len(wave) * 50 * 2

    buffer_out = BytesIO()
    modulate(wave, "IQ_S8", buffer_out)
    result = buffer_out.getvalue()
    # Ensure it's the same size the C++ code expects
    # (But if there's any difference, Python's float computations could differ slightly in length.)
    # We'll just return the full data.

    return result, total_size
