#ifndef HACKRF_TRANSMITTER_H
#define HACKRF_TRANSMITTER_H

#include <string>

#include "logger.h"
#include "config.h"
/**
 * @brief Transmit an IQ_S8 file (int8_t I/Q interleaved) using HackRF.
 *
 * Replicates the behavior of:
 *   hackrf_transfer -f 144390000 -s 2400000 -t pkt.s8 -a 1 -x 40
 *
 * @param filename Path to the .s8 file containing interleaved I/Q samples (signed 8-bit).
 * @return true if transmission completed successfully, false otherwise.
 */
bool transmit_s8_iq_file(const std::string &filename, quill::Logger *logger, Config config);

#endif // HACKRF_TRANSMITTER_H
