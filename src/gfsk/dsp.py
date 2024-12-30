#!/usr/bin/env python3
import math
import cmath
import struct
from typing import List, Tuple
import numpy as np
from src.lib.ringbuffer import Ringbuffer


# Constants
BUFSIZE = 4096
AUDIO_SAMPLE_RATE = 48000  # 48 kHz
BAUD_RATE = 1200
MARK_HZ = 1200
SPACE_HZ = 2200


class FIRInterpolator:
    """
    Polyphase FIR interpolator for upsampling complex I/Q samples.
    
    Attributes:
        interpolation (int): Upsampling factor.
        nfilters (int): Number of polyphase filters.
        ntaps (int): Number of taps per filter.
        xtaps (List[List[float]]): Polyphase filter taps.
    """

    def __init__(self, interpolation: int, taps: List[float]):
        """
        Initialize the FIRInterpolator with the given interpolation factor and filter taps.

        Args:
            interpolation (int): Upsampling factor.
            taps (List[float]): FIR filter taps.

        Raises:
            ValueError: If interpolation factor is less than 1.
        """
        if interpolation < 1:
            raise ValueError("Interpolation factor must be at least 1.")
        
        # Pad taps to make the length a multiple of interpolation
        if len(taps) % interpolation != 0:
            pad = interpolation - (len(taps) % interpolation)
            taps += [0.0] * pad

        self.interpolation = interpolation
        self.nfilters = interpolation
        self.ntaps = len(taps) // interpolation

        # Split taps into polyphase filters
        self.xtaps = [[] for _ in range(self.nfilters)]
        for i, tap in enumerate(taps):
            self.xtaps[i % self.nfilters].append(tap)

    def interpolate(self, input_buf: Ringbuffer, output_list: List[complex]) -> int:
        """
        Perform interpolation by applying polyphase filters to the input buffer.

        Args:
            input_buf (Ringbuffer): Input ring buffer containing complex samples.
            output_list (List[complex]): List to store the interpolated output samples.

        Returns:
            int: Number of input samples consumed.

        Notes:
            - The function processes as many samples as possible given the buffer state.
            - It appends interpolated samples to `output_list`.
        """
        input_size = input_buf.readAvailable()
        if input_size < self.ntaps:
            # Not enough samples to process
            return 0

        processed_count = input_size - self.ntaps + 1
        for i in range(processed_count):
            # Extract the current window of samples
            window = [input_buf[i + k] for k in range(self.ntaps)]
            for j in range(self.nfilters):
                # Apply each polyphase filter
                acc = 0 + 0j
                for k in range(self.ntaps):
                    acc += window[k] * self.xtaps[j][self.ntaps - k - 1]
                output_list.append(acc)
        
        # Remove processed samples from the buffer
        input_buf.remove(processed_count)
        return processed_count


def Izero(x: float) -> float:
    """
    Calculate the 0th order Modified Bessel function of the first kind, I0(x).

    Args:
        x (float): Input value.

    Returns:
        float: Computed I0(x).

    Notes:
        - Uses a series expansion approach.
        - Suitable for small to moderate values of x.
    """
    EPSILON = 1.0e-21
    s = 1.0
    d = 1.0
    y = (x / 2.0) ** 2
    n = 1
    while d > EPSILON * s:
        d *= y / (n * n)
        s += d
        n += 1
    return s


def compute_ntaps(sampling_freq: float, transition_width: float, beta: float) -> int:
    """
    Estimate the number of taps for the Gaussian filter based on sampling frequency,
    transition width, and beta parameter.

    Args:
        sampling_freq (float): Sampling frequency in Hz.
        transition_width (float): Transition width in Hz.
        beta (float): Beta parameter for the Kaiser window.

    Returns:
        int: Estimated number of taps (odd integer).

    Raises:
        ValueError: If any parameter is non-positive.
    """
    if sampling_freq <= 0:
        raise ValueError("Sampling frequency must be positive.")
    if transition_width <= 0:
        raise ValueError("Transition width must be positive.")
    if beta < 0:
        raise ValueError("Beta must be non-negative.")

    a = beta / 0.1102 + 8.7
    ntaps = int(a * sampling_freq / (22.0 * transition_width))
    # Ensure ntaps is odd
    if ntaps % 2 == 0:
        ntaps += 1
    return ntaps


def gaussian_filter(bt: float, samples_per_symbol: int) -> List[float]:
    """
    Generate Gaussian filter taps for GFSK modulation.

    Args:
        bt (float): Bandwidth-Time product.
        samples_per_symbol (int): Number of samples per symbol.

    Returns:
        List[float]: Gaussian filter taps.
    """
    if bt <= 0:
        raise ValueError("Bandwidth-Time product must be positive.")
    if samples_per_symbol < 1:
        raise ValueError("Samples per symbol must be at least 1.")

    t = np.linspace(-0.5, 0.5, samples_per_symbol, endpoint=False)
    sigma = np.sqrt(np.log(2)) / (2 * np.pi * bt)
    h = np.exp(-0.5 * (t / sigma) ** 2)
    h /= np.sum(h)  # Normalize the filter
    return h.tolist()


def lowpass(gain: float, sampling_freq: float, cutoff_freq: float, transition_width: float) -> List[float]:
    """
    Create a lowpass FIR filter using the Kaiser window method.

    Args:
        gain (float): Desired gain at 0 Hz.
        sampling_freq (float): Sampling frequency in Hz.
        cutoff_freq (float): Cutoff frequency in Hz.
        transition_width (float): Transition width in Hz.

    Returns:
        List[float]: Lowpass FIR filter taps.
    """
    if gain <= 0:
        raise ValueError("Gain must be positive.")
    if cutoff_freq <= 0 or cutoff_freq >= sampling_freq / 2:
        raise ValueError("Cutoff frequency must be between 0 and Nyquist frequency.")
    if transition_width <= 0:
        raise ValueError("Transition width must be positive.")

    beta = 7.0  # Kaiser window beta parameter
    ntaps = compute_ntaps(sampling_freq, transition_width, beta)
    taps = gaussian_filter(bt=0.3, samples_per_symbol=ntaps)  # Example: using GFSK's gaussian_filter

    # Generate lowpass filter taps
    w = kaiser(ntaps, beta)
    M = (ntaps - 1) // 2
    fwT0 = 2.0 * math.pi * cutoff_freq / sampling_freq

    lowpass_taps = np.zeros(ntaps)
    for n in range(-M, M + 1):
        idx = n + M
        if n == 0:
            lowpass_taps[idx] = (fwT0 / math.pi) * w[idx]
        else:
            lowpass_taps[idx] = (math.sin(n * fwT0) / (n * math.pi)) * w[idx]
    
    # Normalize the filter to achieve the desired gain at DC
    fmax = np.sum(lowpass_taps)
    if abs(fmax) < 1e-12:
        fmax = 1.0
    norm_factor = gain / fmax
    lowpass_taps *= norm_factor
    return lowpass_taps.tolist()


def kaiser(ntaps: int, beta: float) -> np.ndarray:
    """
    Generate a Kaiser window.

    Args:
        ntaps (int): Number of taps (filter length).
        beta (float): Beta parameter for the Kaiser window.

    Returns:
        np.ndarray: Kaiser window.
    """
    if ntaps <= 0:
        raise ValueError("Number of taps must be positive.")
    if beta < 0:
        raise ValueError("Beta must be non-negative.")

    return np.kaiser(ntaps, beta)


def f32_to_s8(input_data: List[complex]) -> bytearray:
    """
    Convert float I/Q samples in range [-1, 1] to signed 8-bit I/Q pairs.

    Args:
        input_data (List[complex]): List of complex I/Q samples.

    Returns:
        bytearray: Bytearray containing interleaved signed 8-bit I/Q samples.
    """
    out = bytearray()

    for cplx in input_data:
        # Clamp and convert to int8
        re = max(-128, min(127, int(cplx.real * 127.0)))
        im = max(-128, min(127, int(cplx.imag * 127.0)))
        out += struct.pack('bb', re, im)

    return out


def gfsk_modulate(bitstream: List[bool], baud_rate: int, sample_rate: int, freq_deviation: float, bt: float) -> List[complex]:
    """
    Perform GFSK modulation on the given bitstream.

    Args:
        bitstream (List[bool]): List of boolean bits to modulate.
        baud_rate (int): Symbols per second.
        sample_rate (int): Samples per second.
        freq_deviation (float): Frequency deviation in Hz.
        bt (float): Bandwidth-Time product for Gaussian filter.

    Returns:
        List[complex]: List of complex I/Q samples representing the modulated signal.

    Raises:
        ValueError: If any parameter is invalid.
    """
    if baud_rate <= 0:
        raise ValueError("Baud rate must be positive.")
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive.")
    if freq_deviation <= 0:
        raise ValueError("Frequency deviation must be positive.")
    if bt <= 0:
        raise ValueError("Bandwidth-Time product must be positive.")

    # Step 1: Map bits to symbols (-1 and +1)
    symbols = np.array([1 if bit else -1 for bit in bitstream], dtype=float)

    # Step 2: Apply Gaussian filter for pulse shaping
    samples_per_symbol = int(sample_rate / baud_rate)
    gaussian_taps = gaussian_filter(bt, samples_per_symbol)
    filtered_symbols = np.convolve(symbols, gaussian_taps, mode='same')

    # Step 3: Integrate to get phase
    delta_phase = 2.0 * math.pi * freq_deviation / sample_rate
    phase = np.cumsum(filtered_symbols) * delta_phase
    # Wrap phase to [-pi, pi]
    phase = np.mod(phase + np.pi, 2 * np.pi) - np.pi

    # Step 4: Generate I/Q samples
    iq_samples = np.exp(1j * phase)

    return iq_samples.tolist()


def modulate(iq_samples: List[complex], iq_format: str, fout) -> None:
    """
    Write I/Q samples to the output in the specified format.

    Args:
        iq_samples (List[complex]): List of complex I/Q samples.
        iq_format (str): Output format - 'IQ_S8', 'IQ_F32', or 'PCM'.
        fout: File-like object to write the samples to.

    Raises:
        ValueError: If the specified format is unsupported.
    """
    if iq_format not in ["IQ_S8", "IQ_F32", "PCM"]:
        raise ValueError(f"Unsupported IQ format: {iq_format}")

    if iq_format == "IQ_S8":
        # Convert to signed 8-bit I/Q pairs
        data = f32_to_s8(iq_samples)
        fout.write(data)
    elif iq_format == "IQ_F32":
        # Each sample is two float32 numbers (I and Q)
        fmt = 'ff'
        packed_data = b''.join([struct.pack(fmt, c.real, c.imag) for c in iq_samples])
        fout.write(packed_data)
    elif iq_format == "PCM":
        # PCM: Write only the I component as float32
        fmt = 'f'
        packed_data = b''.join([struct.pack(fmt, c.real) for c in iq_samples])
        fout.write(packed_data)
