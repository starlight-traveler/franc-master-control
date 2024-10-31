#include <iostream>
#include <cstring>
#include <csignal>
#include <pybind11/embed.h>
#include <pigpio.h>

#include "logger.h"
#include "version.h"
#include "threading.tpp"
#include "spi_bus.h"

namespace py = pybind11;

/**
 * @brief Setup Signal Handlers
 * 
 * @param signum 
 */

void signalHandler(int signum)
{

  std::cout << "Interrupt signal (" << signum << ") received.\n";
  exit(signum);

}

/**
 * @brief Global variables should be kept to a minimum
 * 
 * Most variables which are global should be used for testing
 */

// Use atomic for synchronization across threads


/**
 * 
 * @fn int main()
 * @brief Main function to enter the program
 *
 * Initializes the system execution and should be considerd as primary
 * "runtime" thread.
 * @return Should never return any value, and run infintely.
 */

int main()
{

  /**
   * @brief Initialize the system
   *
   * Initializes the system logger to capture and log system events. Initializes
   * the signletons that need to be fired once.
   */

    // ----- Pre-execution Runtime Initialization Phase ----- //

    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);
    std::signal(SIGSEGV, signalHandler);

    // Initalize logger
    quill::Logger *logger = initialize_logger();

    // Initialize pigpio library
    if (gpioInitialise() < 0)
    {
      std::cerr << "Failed to initialize pigpio." << std::endl;
      return 1;
    }

    // Initalize current build
    LOG_DEBUG(logger, "Build date: {}", BUILD_DATE);
    LOG_DEBUG(logger, "Project version: {}", PROJECT_VERSION);

    // Initalize pybind
    setenv("PYTHONPATH", "../runnable/", 1);
    py::scoped_interpreter guard{};

  /**
   * @brief Start all tests to make sure functionality exits atomically
   * 
   * Tests will only run if the --tests flag is enabled with the CREATE script
   */

#ifdef RUN_TESTS

    LOG_INFO(logger, "This is running test.");

#else

    // Sensor Thread
    std::thread sensor([&]()
                       { threaded(logger, 5, 3, spiSetup); });

    // // Transmission Thread
    // std::thread transmission([&]()
    //                   { threaded(logger, 5, 3, null, logger); });

    // // Write Thread
    // std::thread write([&]()
    //                   { threaded(logger, 5, 3, null, logger); });

#endif

    return 0;

}