#include "quill/Backend.h"
#include "quill/Frontend.h"
#include "quill/Logger.h"
#include "quill/sinks/ConsoleSink.h"
#include "quill/sinks/FileSink.h"

// (Remove or adjust this header if it's not needed in your project)
#include "logger.h"

#include <utility>

quill::Logger *initialize_logger()
{
    // Start the backend thread
    quill::BackendOptions backend_options;
    quill::Backend::start(backend_options);

    // Configure console sink colours
    quill::ConsoleSink::Colours colours;
    colours.apply_default_colours();
    colours.assign_colour_to_log_level(quill::LogLevel::Info, quill::ConsoleSink::Colours::blue);      // overwrite for INFO
    colours.assign_colour_to_log_level(quill::LogLevel::Warning, quill::ConsoleSink::Colours::yellow); // overwrite for WARNING
    colours.assign_colour_to_log_level(quill::LogLevel::Error, quill::ConsoleSink::Colours::red);      // overwrite for ERROR

    // Create the console sink
    auto console_sink = quill::Frontend::create_or_get_sink<quill::ConsoleSink>("sink_id_1", colours);

    // Create the file sink
    auto file_sink = quill::Frontend::create_or_get_sink<quill::FileSink>(
        "franc_logging.log",
        []()
        {
            quill::FileSinkConfig cfg;
            cfg.set_open_mode('w'); // overwrite on each run
            return cfg;
        }(),
        quill::FileEventNotifier{});

    // Create or get the logger that writes to both sinks
    quill::Logger *logger = quill::Frontend::create_or_get_logger(
        "root",
        {std::move(console_sink), std::move(file_sink)});

    // Change the LogLevel to print everything
    logger->set_log_level(quill::LogLevel::TraceL3);

    return logger;
}
