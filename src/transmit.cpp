#include <hackrf.h>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <unistd.h>

#include "transmitter.h"
#include "logger.h"
#include "config.h"

/**
 * @brief Simple context structure to hold file pointer for the TX callback.
 */
struct HackRfTxContext
{
    FILE *fp = nullptr;
};

/**
 * @brief HackRF TX callback, called repeatedly by the HackRF driver.
 *
 * Reads bytes from the file into HackRF's buffer (I/Q interleaved int8_t).
 * If EOF is reached, returns -1 to stop the stream.
 */
static int tx_callback(hackrf_transfer *transfer)
{
    // Retrieve custom context, contains the file pointer
    HackRfTxContext *ctx = static_cast<HackRfTxContext *>(transfer->tx_ctx);
    if (!ctx || !ctx->fp)
    {
        // Fill with zeros in case the buffer doesn't exist
        std::memset(transfer->buffer, 0, transfer->buffer_length);
        return 0;
    }

    // Read exactly 'transfer->buffer_length' bytes (which is typically 262,144).
    size_t nread = std::fread(transfer->buffer, 1, transfer->buffer_length, ctx->fp);

    if (nread < transfer->buffer_length)
    {
        // We hit EOF (or an error). Fill remainder with zeros.
        if (std::feof(ctx->fp))
        {
            std::memset(transfer->buffer + nread, 0, transfer->buffer_length - nread);
            // Return -1 to signal the HackRF library that we want to stop transmission.
            return -1;
        }
        else
        {
            // A read error occurred; also stop streaming.
            return -1;
        }
    }

    // Returning 0 means "keep streaming."
    return 0;
}

/**
 * @brief Transmits a .s8 file (I/Q interleaved, signed 8-bit) using HackRF at:
 *        - Frequency:  144.39 MHz
 *        - SampleRate: 2.4 MSPS
 *        - Amplifier:  enabled (gain stage)
 *        - TX VGA gain: 40
 *
 * @param filename path to the s8 file
 * @return true on success, false otherwise
 */
bool transmit_s8_iq_file(const std::string &filename, quill::Logger *logger, Config config)
{
    hackrf_device *device = nullptr;

    // 1. Initialize HackRF
    int result = hackrf_init();
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_init() failed: {}", hackrf_error_name((hackrf_error)result));
        return false;
    }

    // 2. Open HackRF device
    result = hackrf_open(&device);
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_open() failed: {}", hackrf_error_name((hackrf_error)result));
        hackrf_exit();
        return false;
    }

    // 3. Set frequency (144.390 MHz)
    const uint64_t freq_hz = config.frequency;
    LOG_DEBUG(logger, "Frequency set: {}", freq_hz);
    result = hackrf_set_freq(device, freq_hz);
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_set_freq() failed: {}", hackrf_error_name((hackrf_error)result));
        hackrf_close(device);
        hackrf_exit();
        return false;
    }

    // 4. Set sample rate (2.4 MSPS)
    const double sample_rate_hz = config.sampleRate;
    LOG_DEBUG(logger, "Sample rate set: {}", sample_rate_hz);
    result = hackrf_set_sample_rate(device, sample_rate_hz);
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_set_sample_rate() failed: {}", hackrf_error_name((hackrf_error)result));
        hackrf_close(device);
        hackrf_exit();
        return false;
    }

    // 5. Enable amplifier (-a 1)
    result = hackrf_set_amp_enable(device, config.amplifier);
    LOG_DEBUG(logger, "Amplifier enable: {}", result);
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_set_amp_enable(): {}", hackrf_error_name((hackrf_error)result));
        hackrf_close(device);
        hackrf_exit();
        return false;
    }

    // 6. Set TX VGA gain to 40 (-x 40)
    const int txvga_gain = config.txvga_gain;
    LOG_DEBUG(logger, "Internal gain set: {}", txvga_gain);
    result = hackrf_set_txvga_gain(device, txvga_gain);
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_set_txvga_gain(): {}", hackrf_error_name((hackrf_error)result));
        hackrf_close(device);
        hackrf_exit();
        return false;
    }

    // (Optional) You can set LNA gain or baseband filter here if needed:
    // hackrf_set_lna_gain(device, 8); // Example
    // hackrf_set_baseband_filter_bandwidth(device, 1750000); // Example

    // 7. Open the .s8 file
    FILE *fp = std::fopen(filename.c_str(), "rb");
    if (!fp)
    {
        LOG_CRITICAL(logger, "Failed to open file: {}", filename);
        hackrf_close(device);
        hackrf_exit();
        return false;
    }

    // 8. Prepare context (pass file pointer to callback)
    HackRfTxContext ctx;
    ctx.fp = fp;

    // 9. Start TX streaming
    result = hackrf_start_tx(device, tx_callback, &ctx);
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_start_tx() failed: {}", hackrf_error_name((hackrf_error)result));
        std::fclose(fp);
        hackrf_close(device);
        hackrf_exit();
        return false;
    }

    // 10. Wait until streaming stops (callback returns -1 at EOF).
    while (hackrf_is_streaming(device) == HACKRF_TRUE)
    {
        // Sleep briefly so we don't busy-wait.
        usleep(50000); // 50 ms
    }

    // 11. Cleanly stop TX
    result = hackrf_stop_tx(device);
    if (result != HACKRF_SUCCESS)
    {
        LOG_CRITICAL(logger, "hackrf_stop_tx() failed: {}", hackrf_error_name((hackrf_error)result));
        std::fclose(fp);
        hackrf_close(device);
        hackrf_exit();
        return false;
    }

    // 12. Cleanup
    std::fclose(fp);
    hackrf_close(device);
    hackrf_exit();

    LOG_INFO(logger, "Finished transmitting: {}", filename);
    return true;
}
