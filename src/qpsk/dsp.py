#!/usr/bin/env python3

import sys
import logging
import math
import numpy as np
from commpy.channelcoding.convcode import Trellis, conv_encode, viterbi_decode

logger = logging.getLogger(__name__)

# Generator polynomials for the convolutional encoder
G = np.array([[0o7, 0o5]])  # Example for rate 1/2, constraint length 3
M = np.array([2])  # Memory of the convolutional code

def convolutional_encode(bits):
    """
    Encode bits using a convolutional code.
    """
    trellis = Trellis(M, G)
    return conv_encode(bits, trellis)

def rrc_filter(beta, sps, num_taps):
    """
    Generates a Root Raised Cosine (RRC) filter.
    
    :param beta: Roll-off factor (0 <= beta <= 1).
    :param sps: Samples per symbol.
    :param num_taps: Number of taps in the filter.
    :return: An array containing the filter coefficients.
    """
    t = np.arange(num_taps) - num_taps // 2
    rrc = np.zeros_like(t, dtype=float)

    for i in range(len(t)):
        if t[i] == 0.0:
            rrc[i] = 1.0 + beta * (4 / np.pi - 1)
        elif abs(t[i]) == sps / (4 * beta):
            rrc[i] = (beta / np.sqrt(2)) * (((1 + 2 / np.pi) *
                    (np.sin(np.pi / (4 * beta)))) + ((1 - 2 / np.pi) *
                    (np.cos(np.pi / (4 * beta)))))
        else:
            rrc[i] = (np.sin(np.pi * t[i] * (1 - beta) / sps) + 
                      4 * beta * t[i] / sps * np.cos(np.pi * t[i] * (1 + beta) / sps)) / \
                     (np.pi * t[i] / sps * (1 - (4 * beta * t[i] / sps)**2))
    
    return rrc / np.sqrt(np.sum(rrc**2))  # Normalize filter power

def qpsk_modulate(bits, sps=10, beta=0.25, num_taps=101):
    """
    QPSK modulator with RRC pulse shaping and simulated impairments.
    
    :param bits: Input bitstream.
    :param sps: Samples per symbol (upsampling factor).
    :param beta: Roll-off factor for the RRC filter.
    :param num_taps: Number of taps in the RRC filter.
    :return: Array of complex modulated symbols.
    """
    # Ensure even number of bits
    if len(bits) % 2 != 0:
        bits.append(0)

    # QPSK Symbol mapping
    symbols = np.array([1+1j, 1-1j, -1+1j, -1-1j])  # Mapping: 00, 01, 10, 11
    dibits = np.array(bits).reshape(-1, 2)
    index = 2 * dibits[:, 0] + dibits[:, 1]
    symbols = symbols[index]

    # Upsample symbols
    upsampled = np.zeros(len(symbols) * sps, dtype=complex)
    upsampled[::sps] = symbols

    # RRC Pulse Shaping
    rrc_coeffs = rrc_filter(beta, sps, num_taps)
    shaped = np.convolve(upsampled, rrc_coeffs, mode='same')

    # Simulate Carrier Frequency Offset
    frequency_offset = 0.01  # Fraction of the sampling rate
    t = np.arange(len(shaped))
    carrier = np.exp(2j * np.pi * frequency_offset * t / sps)
    shaped *= carrier

    return shaped

def qpsk_modulator(input_source, config, parse_bitstream_func, transmit_func=None):
    """
    QPSK modulator orchestration:
      - Use parse_bitstream_func to get a list of booleans or 0/1 bits.
      - Perform QPSK modulation.
      - Output to file/stdout or transmit via HackRF.

    :param input_source: 'str:<bitstring>' or 'file:<filepath>'
    :param config: Dictionary with keys like:
        {
          'samples_per_symbol': '4',
          'output': 'hackrf' or 'file:filename' or 'stdout',
          'format': 'f32' or 's8',
          (hackrf config if output='hackrf'),
          'debug': True/False
        }
    :param parse_bitstream_func: A function reference that parses the bitstream 
                                 (like your existing parse_bitstream).
    :param transmit_func: Optional function reference to transmit via HackRF.
    """
    debug = config.get('debug', False)
    samples_per_symbol = int(config.get('samples_per_symbol', 4))

    bits = parse_bitstream_func(input_source)  # e.g., returns list of booleans
    if debug:
        logger.debug(f"[QPSK] Input bits: {len(bits)} bits. SPS={samples_per_symbol}")

    # Perform QPSK
    iq_samples = qpsk_modulate(bits, samples_per_symbol)

    out_target = config.get('output', 'stdout').lower()
    out_format = config.get('format', 'f32').lower()

    # If HackRF output
    if out_target == 'hackrf':
        if transmit_func is None:
            logger.error("[QPSK] transmit_func not provided for HackRF output.")
            sys.exit(1)
        # Transmit
        transmit_func(iq_samples, config)
        return

    # Otherwise, file or stdout
    if out_format not in ["f32", "s8"]:
        logger.warning(f"[QPSK] Unknown output format '{out_format}', defaulting to 'f32'.")
        out_format = "f32"

    # Interleave
    interleaved = np.empty(iq_samples.size * 2, dtype=np.float32)
    interleaved[0::2] = np.real(iq_samples)
    interleaved[1::2] = np.imag(iq_samples)

    if out_target.startswith('file:'):
        filepath = out_target[5:]
        try:
            fout = open(filepath, 'wb')
            logger.info(f"[QPSK] Writing output to file '{filepath}'")
        except IOError:
            logger.error(f"[QPSK] Error creating output file '{filepath}'")
            sys.exit(1)
    else:
        fout = sys.stdout.buffer
        logger.info("[QPSK] Writing output to stdout")

    if out_format == "s8":
        scaled = np.round(interleaved * 127).astype(np.int8)
        fout.write(scaled.tobytes())
    else:  # "f32"
        fout.write(interleaved.tobytes())

    if fout is not sys.stdout.buffer:
        fout.close()

    if debug:
        logger.info("[QPSK] Modulation complete.")
