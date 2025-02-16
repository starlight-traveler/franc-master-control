#ifndef CONFIG_H
#define CONFIG_H

#include <string>
#include "aprs.h"
#include "logger.h"

/**
 * @brief Configuration struct for the entire program.
 */
struct Config
{
    // "main" section
    bool debug;
    std::string callsign;
    std::string dest;
    std::string path;
    std::string output;
    std::string info;
    OutputFormat iq_sf;

    // "hackrf" section, for example
    double frequency;  // e.g. 144390000 for 144.39 MHz (you can store in Hz)
    double sampleRate; // e.g. 2e6 = 2 MHz sample rate, etc.
    int amplifier;
    int txvga_gain;
};

/**
 * @brief Loads configuration data from file
 *        If the file does not exist, it uses the built-in defaults automatically.
 *
 * @param cfgFile Path to .cfg file (INI‐style).
 * @return Populated Config struct with either file‐based or default values.
 */
Config load_config(const std::string &cfgFile, quill::Logger *logger);

/**
 * @brief Prints out the loaded configuration (for debugging).
 */
void print_config(const Config &config);

#endif
