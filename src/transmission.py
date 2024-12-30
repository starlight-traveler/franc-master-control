import sys
import numpy as np
import time
import logging

from python_hackrf import pyhackrf

logger = logging.getLogger(__name__)

'''
##################
HackRF (PyHackRF)
##################
'''

def transmit_hackrf(iq_samples, config):
    """
    Transmit I/Q samples using HackRF via PyHackRF.

    :param iq_samples: Complex samples to transmit (list or np.ndarray of np.complex64)
    :param config: Dictionary with HackRF config:
       {
         'frequency': float,    # e.g. 100e6
         'sample_rate': float,  # e.g. 10e6
         'if_gain': int,        # 0 - 47 dB in 1 dB steps (TX side)
         'rf_amp': bool,        # True/False -> 11 dB amp
         'use_external_clk': bool  # If True, user wants external 10 MHz on CLKIN
       }
    """

    # -------------------------------------------------------------------------
    # 1) Parse and Validate Config
    # -------------------------------------------------------------------------
    frequency     = float(config.get('frequency', 100e6))
    sample_rate   = float(config.get('sample_rate', 10e6))
    if_gain       = int(config.get('if_gain', 20))     # 0 - 47 dB
    rf_amp        = bool(config.get('rf_amp', True))   # 0 or 11 dB
    use_ext_clk   = bool(config.get('use_external_clk', False))

    # Safety check: HackRF typically supports ~2 MHz to ~20 MHz sample_rate
    if not 2e6 <= sample_rate <= 20e6:
        logger.warning("Sample rate %.1f Hz is outside recommended 2-20 MHz range.", sample_rate)

    # -------------------------------------------------------------------------
    # 2) Convert and Normalize I/Q Samples
    # -------------------------------------------------------------------------
    # Ensure we have a np.ndarray of type complex64
    if not isinstance(iq_samples, np.ndarray):
        iq_samples = np.array(iq_samples, dtype=np.complex64)
    else:
        iq_samples = iq_samples.astype(np.complex64)

    # Interleave (float32, float32) -> [I, Q, I, Q, ...]
    interleaved = np.empty(iq_samples.size * 2, dtype=np.float32)
    interleaved[0::2] = np.real(iq_samples)
    interleaved[1::2] = np.imag(iq_samples)

    # Normalize to [-1, 1]
    peak = np.max(np.abs(interleaved))
    if peak > 0:
        interleaved /= peak

    # Convert float32 range [-1,1] -> int8 range [-127,127]
    interleaved_int8 = np.round(interleaved * 127).astype(np.int8)

    # We'll iterate this buffer in a loop (circularly).
    tx_index = 0

    # -------------------------------------------------------------------------
    # 3) Initialize HackRF
    # -------------------------------------------------------------------------
    try:
        pyhackrf.pyhackrf_init()
    except Exception as exc:
        logger.error("Could not init PyHackRF library: %s", exc)
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 4) Open the HackRF Device
    # -------------------------------------------------------------------------
    device: pyhackrf.PyHackrfDevice = pyhackrf.pyhackrf_open()
    if device is None:
        logger.error("No HackRF device found or could not be opened.")
        pyhackrf_exit()
        sys.exit(1)

    try:
        # ---------------------------------------------------------------------
        # 5) (Optional) If Using External 10 MHz Reference
        # ---------------------------------------------------------------------
        # In many firmware versions, there's no direct "set_clk_source" method
        # at Python level. Typically, you rely on hackrf_clock or the presence
        # of a 10 MHz square wave on CLKIN. The HackRF automatically switches
        # to CLKIN upon next TX/RX start if it detects a valid signal.
        #
        # For demonstration, we'll just log it. If your version of python_hackrf
        # has a function like `device.pyhackrf_set_clkout_enable()` or
        # `device.pyhackrf_set_hw_sync_mode()`, you could call it here:
        #
        # Example:
        #   device.pyhackrf_set_clkout_enable(True)   # 10 MHz clock on CLKOUT

        if use_ext_clk:
            logger.info("Expecting external 10 MHz clock on CLKIN (auto-switch).")

        # ---------------------------------------------------------------------
        # 6) Configure HackRF
        # ---------------------------------------------------------------------
        # Gains:
        #   - pyhackrf_set_amp_enable(True/False) => ~11 dB TX RF amp
        #   - pyhackrf_set_txvga_gain(value) => 0 - 47 dB
        #
        # Frequency, Sample Rate, etc.

        device.pyhackrf_set_freq(frequency)                 # LO freq
        device.pyhackrf_set_sample_rate(sample_rate)        # Sample Rate
        device.pyhackrf_set_baseband_filter_bandwidth(
            min(int(sample_rate), 20000000)                 # e.g. ~0.75 * sample_rate in many usage
        )
        device.pyhackrf_set_amp_enable(rf_amp)
        device.pyhackrf_set_txvga_gain(if_gain)

        logger.info("HackRF Config:")
        logger.info("  Frequency: %f Hz", frequency)
        logger.info("  Sample Rate: %f Hz", sample_rate)
        logger.info("  TX IF Gain: %d dB", if_gain)
        logger.info("  RF Amp Enabled: %s", rf_amp)
        logger.info("  External Clock: %s", use_ext_clk)

        # ---------------------------------------------------------------------
        # 7) Define and Register the TX Callback
        # ---------------------------------------------------------------------
        # The signature in the class is:
        #   def set_tx_callback(self, tx_callback_function: Callable[[Self, np.ndarray, int, int], tuple[int, np.ndarray, int]]) -> None
        #
        # We'll fill 'buffer' with our data and return (0, buffer, new_valid_len)
        # returning 0 indicates "continue streaming".
        #
        # The HackRF expects data in int8 I/Q pairs. So 1 complex sample = 2 bytes.

        def tx_callback(dev: pyhackrf.PyHackrfDevice, buffer: np.ndarray, max_len: int, current_len: int):
            nonlocal tx_index
            nonlocal interleaved_int8

            # # of complex samples we can fit into 'max_len' bytes:
            needed_samples = max_len // 2  # each complex sample = 2 bytes (I8, Q8)

            out_end = tx_index + needed_samples
            if out_end > len(interleaved_int8):
                # Wrap around (circular buffer)
                remainder = out_end - len(interleaved_int8)
                block1 = interleaved_int8[tx_index:]
                block2 = interleaved_int8[:remainder]
                data_out = np.concatenate((block1, block2))
                tx_index = remainder
            else:
                data_out = interleaved_int8[tx_index:out_end]
                tx_index = out_end

            # buffer is np.uint8 in the extension. If your extension truly supports
            # signed int8 interpretation, we can do a view(...) or we might offset.
            # We'll do direct reinterpretation:
            data_u8 = data_out.view(np.uint8)

            # Safety check
            if len(data_u8) > max_len:
                logger.warning("Data to fill is bigger than buffer. Shouldn't happen.")
                return (1, buffer, 0)

            # Copy into buffer
            buffer[:len(data_u8)] = data_u8
            new_valid_length = len(data_u8)

            # Return 0 to continue streaming
            return (0, buffer, new_valid_length)

        device.set_tx_callback(tx_callback)

        # ---------------------------------------------------------------------
        # 8) Start Transmission
        # ---------------------------------------------------------------------
        device.pyhackrf_start_tx()
        logger.info("[HackRF] Transmission started. Press Ctrl+C to stop...")

        # Keep the script alive indefinitely (or until user interrupts).
        while True:
            # Let Python handle KeyboardInterrupt
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("[HackRF] Transmission interrupted by user.")
    except Exception as exc:
        logger.error("[HackRF] Exception in TX loop: %s", exc, exc_info=True)
    finally:
        # ---------------------------------------------------------------------
        # 9) Stop TX, Close Device, Exit the Library
        # ---------------------------------------------------------------------
        try:
            device.pyhackrf_stop_tx()
        except:
            pass
        try:
            device.pyhackrf_close()
        except:
            pass

        pyhackrf.pyhackrf_exit()
        logger.info("[HackRF] Device closed. Library exited.")