#include "config.h"

#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <cstdlib>

// ------------------------------------------------------------------
// Helper: trim() removes leading and trailing whitespace from a string
// ------------------------------------------------------------------
static inline void trim(std::string &s)
{
    // Left trim
    s.erase(s.begin(), std::find_if(s.begin(), s.end(),
                                    [](unsigned char ch)
                                    { return !std::isspace(ch); }));
    // Right trim
    s.erase(std::find_if(s.rbegin(), s.rend(),
                         [](unsigned char ch)
                         { return !std::isspace(ch); })
                .base(),
            s.end());
}

// ------------------------------------------------------------------
// set_defaults() sets the built-in default values ("automatic mode")
// ------------------------------------------------------------------
static void set_defaults(Config &config)
{
    // Main section defaults.
    config.debug = false;
    config.callsign = "KD9WPR";
    config.dest = "APRS";
    config.path = "WIDE1-1,WIDE2-1";
    config.output = "pkt8.s8";
    config.info = "Hello from default config!";
    config.iq_sf = IQ_S8;
    config.amplifier = 1;
    config.txvga_gain = 40;

    // HackRF section defaults.
    config.frequency = 144390000.0; // 144.390 MHz
    config.sampleRate = 2000000.0;  // 2 MHz
}

// ------------------------------------------------------------------
// set_value() updates the config struct for a given [section] key/value pair
// ------------------------------------------------------------------
static void set_value(Config &config, const std::string &section,
                      const std::string &key, const std::string &val)
{
    // For robust matching, compare lowercase versions.
    std::string lowerSec = section;
    std::string lowerKey = key;
    std::transform(lowerSec.begin(), lowerSec.end(), lowerSec.begin(), ::tolower);
    std::transform(lowerKey.begin(), lowerKey.end(), lowerKey.begin(), ::tolower);

    if (lowerSec == "main")
    {
        if (lowerKey == "debug")
        {
            config.debug = (val == "true" || val == "1");
        }
        else if (lowerKey == "callsign")
        {
            config.callsign = val;
        }
        else if (lowerKey == "dest")
        {
            config.dest = val;
        }
        else if (lowerKey == "path")
        {
            config.path = val;
        }
        else if (lowerKey == "output")
        {
            config.output = val;
        }
        else if (lowerKey == "info")
        {
            config.info = val;
        }
        else if (lowerKey == "sample_format")
        {
            if (val == "s8")
                config.iq_sf = IQ_S8;
            else if (val == "f32")
                config.iq_sf = IQ_F32;
            else if (val == "pcm")
                config.iq_sf = PCM_F32;
        }
    }
    else if (lowerSec == "hackrf")
    {
        if (lowerKey == "frequency")
        {
            config.frequency = std::strtod(val.c_str(), nullptr);
        }
        else if (lowerKey == "samplerate" || lowerKey == "sample_rate")
        {
            config.sampleRate = std::strtod(val.c_str(), nullptr);
        }
        else if (lowerKey == "amplifier")
        {
            config.amplifier = std::strtod(val.c_str(), nullptr);
        }
        else if (lowerKey == "txvga_gain")
        {
            config.txvga_gain = std::strtod(val.c_str(), nullptr);
        }
    }
}

// ------------------------------------------------------------------
// load_config() opens and parses the INI-style file (if it exists)
// ------------------------------------------------------------------
Config load_config(const std::string &cfgFile, quill::Logger *logger)
{
    Config config;
    set_defaults(config); // first, load all defaults

    std::ifstream infile(cfgFile);
    if (!infile.is_open())
    {
        LOG_CRITICAL(logger,"Config file '{}' not found. Using built-in defaults", cfgFile);
        return config;
    }

    std::string line;
    std::string currentSection = "main"; // default section

    while (std::getline(infile, line))
    {
        // Remove comments starting with '#' or ';'
        auto commentPos = line.find('#');
        if (commentPos != std::string::npos)
            line.erase(commentPos);
        commentPos = line.find(';');
        if (commentPos != std::string::npos)
            line.erase(commentPos);

        trim(line);
        if (line.empty())
            continue;

        // If the line is a section header, e.g., [hackrf]
        if (line.front() == '[' && line.back() == ']')
        {
            currentSection = line.substr(1, line.size() - 2);
            trim(currentSection);
            continue;
        }

        // Otherwise, expect a key=value pair.
        auto eqPos = line.find('=');
        if (eqPos == std::string::npos)
            continue; // skip malformed lines

        std::string key = line.substr(0, eqPos);
        std::string value = line.substr(eqPos + 1);
        trim(key);
        trim(value);

        if (!key.empty())
            set_value(config, currentSection, key, value);
    }

    infile.close();
    return config;
}

// ------------------------------------------------------------------
// print_config() prints out the loaded configuration (for debugging)
// ------------------------------------------------------------------
void print_config(const Config &config)
{
    std::cout << "=== Loaded Configuration ===\n";
    std::cout << "[main]\n";
    std::cout << "  debug         = " << (config.debug ? "true" : "false") << "\n";
    std::cout << "  callsign      = " << config.callsign << "\n";
    std::cout << "  dest          = " << config.dest << "\n";
    std::cout << "  path          = " << config.path << "\n";
    std::cout << "  output        = " << config.output << "\n";
    std::cout << "  info          = " << config.info << "\n";
    std::cout << "  sample_format = ";
    switch (config.iq_sf)
    {
    case IQ_S8:
        std::cout << "s8\n";
        break;
    case IQ_F32:
        std::cout << "f32\n";
        break;
    case PCM_F32:
        std::cout << "pcm\n";
        break;
    }
    std::cout << "\n[hackrf]\n";
    std::cout << "  frequency  = " << config.frequency << "\n";
    std::cout << "  sampleRate = " << config.sampleRate << "\n";
    std::cout << "============================\n\n";
}
