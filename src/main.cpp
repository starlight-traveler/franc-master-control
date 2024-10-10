#include <iostream>
#include <cstring>
#include <csignal>

#include "logger.h"
#include "version.h"

// namespace py = pybind11;

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
 * @brief Main function to enter the program, should be classified as main thread
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

    // Initalize current build
    LOG_DEBUG(logger, "Build date: {}", BUILD_DATE);
    LOG_DEBUG(logger, "Project version: {}", PROJECT_VERSION);

    // Initalize pybind
    setenv("PYTHONPATH", "../runnable/", 1);
    // py::scoped_interpreter guard{};

  /**
   * @brief Start all tests to make sure functionality exits atomically
   *
   * All tests should run to make sure no threading issues or post-compilation
   * issues occur.
   */

#ifdef RUN_TESTS

    LOG_INFO(logger, "This is running test.");

#else    

    LOG_INFO(logger, "Hello World!");

#endif

    return 0;

}