#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <unistd.h>
#include <iostream>

#include "logger.h"
#include "aprs.h"
#include "transmitter.h"
#include "config.h"
#include "interconnect.h"
#include "master_sensor_struct.h"
#include "json.hpp"

using json = nlohmann::json;

// ---------------------------------------------------------------------
// USAGE FUNCTION
// ---------------------------------------------------------------------
// Prints out the usage instructions if the user enters an invalid flag.
static void usage(quill::Logger *logger)
{
    LOG_INFO(logger, "Usage: FRANC [options] <message>");
    LOG_INFO(logger, "  -c <callsign>            : Set callsign (e.g. N0CALL)");
    LOG_INFO(logger, "  -d <destination>         : Set destination (default APRS)");
    LOG_INFO(logger, "  -p <path>                : Set path (default WIDE1-1,WIDE2-1)");
    LOG_INFO(logger, "  -o <output file>         : Set output file name (default stdout)");
    LOG_INFO(logger, "  -f <sample format>       : Set sample format (s8, f32, pcm)");
    LOG_INFO(logger, "  -v                       : Enable debug messages");
    LOG_INFO(logger, "  <message>                : The APRS information field/message");
}

// ---------------------------------------------------------------------
// FUNCTION: override_config_from_args
// PURPOSE: If the user provided command-line flags, use them to override
//          values that were loaded from the configuration file.
// ---------------------------------------------------------------------
void override_config_from_args(quill::Logger *logger, int argc, char *argv[], Config &config)
{
    // Reset getopt's index (in case it was used before)
    optind = 1;
    int opt;
    while ((opt = ::getopt(argc, argv, "c:d:p:o:f:v")) != -1)
    {
        switch (opt)
        {
        case 'c':
            // Override callsign with the flag value.
            config.callsign = optarg;
            break;
        case 'd':
            // Override destination.
            config.dest = optarg;
            break;
        case 'p':
            // Override path.
            config.path = optarg;
            break;
        case 'o':
            // Override output file name.
            config.output = optarg;
            break;
        case 'f':
            // Override sample format.
            if (std::strcmp(optarg, "s8") == 0)
            {
                config.iq_sf = IQ_S8;
            }
            else if (std::strcmp(optarg, "f32") == 0)
            {
                config.iq_sf = IQ_F32;
            }
            else if (std::strcmp(optarg, "pcm") == 0)
            {
                config.iq_sf = PCM_F32;
            }
            else
            {
                LOG_ERROR(logger, "Incorrect sample format: {}", optarg);
                std::exit(1);
            }
            break;
        case 'v':
            // Enable debugging.
            config.debug = true;
            break;
        default:
            usage(logger);
            std::exit(1);
        }
    }
    // Any remaining non-option argument is assumed to be the APRS message.
    if (optind < argc)
    {
        config.info = argv[optind];
    }
}

// ---------------------------------------------------------------------
// FUNCTION: run_aprs
// PURPOSE: Build the AX.25 frame, process it, and write the output file.
// ---------------------------------------------------------------------
int run_aprs(quill::Logger *logger, const Config &config)
{
    // Use the configuration values; if a particular value is empty,
    // fall back to a hard-coded default.
    const std::string callsignUsed = (!config.callsign.empty() ? config.callsign : "KD9WPR");
    const std::string infoUsed = (!config.info.empty() ? config.info : "Hello from APRS default message");

    LOG_INFO(logger, "===========================");
    LOG_DEBUG(logger, "Using callsign: {}", callsignUsed);
    LOG_DEBUG(logger, "Using destination: {}", config.dest);
    LOG_DEBUG(logger, "Using path: {}", config.path);
    LOG_DEBUG(logger, "Using output file: {}", (!config.output.empty() ? config.output : "stdout"));
    LOG_DEBUG(logger, "Using sample format: {}",
              (config.iq_sf == IQ_S8 ? "IQ_S8" : config.iq_sf == IQ_F32 ? "IQ_F32"
                                                                        : "PCM_F32"));
    LOG_DEBUG(logger, "Using message: {}", infoUsed);

    // Build the AX.25 frame. Assume that ax25frame() accepts C-string parameters.
    auto frame = ax25frame(callsignUsed.c_str(),
                           config.dest.c_str(),
                           (char*)config.path.c_str(),
                           infoUsed.c_str(),
                           false);
    auto frame_nrzi = nrzi(frame);
    auto wave = afsk(frame_nrzi);

    // Open the output file; if none was specified, default to stdout.
    FILE *fout = stdout;
    if (!config.output.empty())
    {
        fout = std::fopen(config.output.c_str(), "wb");
        if (!fout)
        {
            LOG_ERROR(logger, "Error creating output file '{}'", config.output);
            return 1;
        }
    }

    // Write the processed data using the selected sample format.
    if (config.iq_sf == PCM_F32)
    {
        std::fwrite(wave.data(), sizeof(float), wave.size(), fout);
    }
    else
    {
        modulate(wave, fout, config.iq_sf);
    }

    // If output is not stdout, close the file.
    if (fout != stdout)
    {
        std::fclose(fout);
    }

    LOG_INFO(logger, "APRS processing finished successfully.");
    return 0;
}

// ---------------------------------------------------------------------
// MAIN FUNCTION
// PURPOSE: Initialize the logger, load configuration from the file,
//          override with command-line flags if provided, then process
//          and transmit the APRS data.
// ---------------------------------------------------------------------
int main(int argc, char *argv[])
{
    // Initialize the logger.
    quill::Logger *logger = initialize_logger();
    LOG_INFO(logger, "FRANC program initializing...");

    // -----------------------------------------------------------------
    // Step 1. Load the configuration from "franc.cfg".
    //         This loads built-in defaults if the config file is missing.
    // -----------------------------------------------------------------
    const std::string configFile = "/local/franc/franc-master-control/config.cfg";
    Config config = load_config(configFile, logger);

    // -----------------------------------------------------------------
    // Step 2. If any command-line flags are provided, override the
    //         configuration values loaded from the config file.
    // -----------------------------------------------------------------
    if (argc > 1)
    {
        override_config_from_args(logger, argc, argv, config);
    }

    // -----------------------------------------------------------------
    // Step 3. If debugging is enabled, print out the final configuration.
    // -----------------------------------------------------------------
    if (config.debug)
    {
        LOG_INFO(logger, "Debug is enabled; printing configuration...");
        // print_config(config);
    }

    int fd = interconnect_handshake(logger);
    if (fd < 0)
    {
        LOG_ERROR(logger, "Interconnect handshake failed, exiting.");
        return 1;
    }

    // Loop forever: poll the serial bus once every second, update config.info
    // with any received JSON message (if the JSON contains an "info" field),
    // then process and transmit APRS data.
    while (true)
    {
        std::string jsonMsg = request_json(fd);
        if (!jsonMsg.empty())
        {
            try
            {
                json j = json::parse(jsonMsg);
                if (j.contains("timestamp"))
                {
                    // Create an instance of our master structure and populate it.
                    MasterSensorData sensorData;
                    sensorData.timestamp = j.value("timestamp", 0);

                    sensorData.bme_temperature = j.value("bme_temperature", 0.0f);
                    sensorData.bme_pressure = j.value("bme_pressure", 0.0f);
                    sensorData.bme_humidity = j.value("bme_humidity", 0.0f);
                    sensorData.bme_gas_resistance = j.value("bme_gas_resistance", 0.0f);
                    sensorData.bme_altitude = j.value("bme_altitude", 0.0f);

                    sensorData.ens_aqi = j.value("ens_aqi", 0);
                    sensorData.ens_tvoc = j.value("ens_tvoc", 0);
                    sensorData.ens_eco2 = j.value("ens_eco2", 0);
                    sensorData.ens_hp0 = j.value("ens_hp0", 0.0f);
                    sensorData.ens_hp1 = j.value("ens_hp1", 0.0f);
                    sensorData.ens_hp2 = j.value("ens_hp2", 0.0f);
                    sensorData.ens_hp3 = j.value("ens_hp3", 0.0f);

                    sensorData.lsm_accel_x = j.value("lsm_accel_x", 0.0f);
                    sensorData.lsm_accel_y = j.value("lsm_accel_y", 0.0f);
                    sensorData.lsm_accel_z = j.value("lsm_accel_z", 0.0f);
                    sensorData.lsm_gyro_x = j.value("lsm_gyro_x", 0.0f);
                    sensorData.lsm_gyro_y = j.value("lsm_gyro_y", 0.0f);
                    sensorData.lsm_gyro_z = j.value("lsm_gyro_z", 0.0f);

                    sensorData.mpl_pressure = j.value("mpl_pressure", 0.0f);
                    sensorData.mpl_altitude = j.value("mpl_altitude", 0.0f);

                    sensorData.bno_accel_x = j.value("bno_accel_x", 0.0f);
                    sensorData.bno_accel_y = j.value("bno_accel_y", 0.0f);
                    sensorData.bno_accel_z = j.value("bno_accel_z", 0.0f);
                    sensorData.bno_mag_x = j.value("bno_mag_x", 0.0f);
                    sensorData.bno_mag_y = j.value("bno_mag_y", 0.0f);
                    sensorData.bno_mag_z = j.value("bno_mag_z", 0.0f);
                    sensorData.bno_gyro_x = j.value("bno_gyro_x", 0.0f);
                    sensorData.bno_gyro_y = j.value("bno_gyro_y", 0.0f);
                    sensorData.bno_gyro_z = j.value("bno_gyro_z", 0.0f);
                    sensorData.bno_euler_heading = j.value("bno_euler_heading", 0.0f);
                    sensorData.bno_euler_roll = j.value("bno_euler_roll", 0.0f);
                    sensorData.bno_euler_pitch = j.value("bno_euler_pitch", 0.0f);
                    sensorData.bno_linear_accel_x = j.value("bno_linear_accel_x", 0.0f);
                    sensorData.bno_linear_accel_y = j.value("bno_linear_accel_y", 0.0f);
                    sensorData.bno_linear_accel_z = j.value("bno_linear_accel_z", 0.0f);
                    sensorData.bno_gravity_x = j.value("bno_gravity_x", 0.0f);
                    sensorData.bno_gravity_y = j.value("bno_gravity_y", 0.0f);
                    sensorData.bno_gravity_z = j.value("bno_gravity_z", 0.0f);
                    sensorData.bno_calibration_system = j.value("bno_calibration_system", 0);
                    sensorData.bno_calibration_gyro = j.value("bno_calibration_gyro", 0);
                    sensorData.bno_calibration_accel = j.value("bno_calibration_accel", 0);
                    sensorData.bno_calibration_mag = j.value("bno_calibration_mag", 0);

                    LOG_INFO(logger, "Timestamp: {}", sensorData.timestamp);
                    LOG_INFO(logger, "BME688 Temperature: {}", sensorData.bme_temperature);
                    LOG_INFO(logger, "ENS160 AQI: {}", sensorData.ens_aqi);
                }

                else
                {
                    LOG_INFO(logger, "JSON matching error.");
                    config.info = "";
                }
            }
            catch (std::exception &e)
            {
                LOG_ERROR(logger, "JSON parse error: {}", e.what());
                config.info = "";
            }
        }
        else
        {
            LOG_ERROR(logger, "JSON empty.");
            config.info = "";
        }

        int result = run_aprs(logger, config);

        std::string s8File = (!config.output.empty() ? config.output : "pkt8.s8");
        LOG_INFO(logger, "===========================");
        LOG_INFO(logger, "Started transmission of {}", s8File);

        // // bool success = transmit_s8_iq_file(s8File, logger, config);
        // if (!success)
        // {
        //     LOG_CRITICAL(logger, "Transmission failed");
        // }
        // else
        // {
        //     LOG_INFO(logger, "Transmission completed successfully");
        // }

        sleep(1); // Wait 1 second before the next cycle.
    }

    close(fd);
    return 0;
}