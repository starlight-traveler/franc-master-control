cmake_minimum_required(VERSION 3.10)

#
# Project definition
#
project(FRANC VERSION 1.0.0 LANGUAGES CXX)

#
# Set and enforce CMake policies
#
cmake_policy(SET CMP0054 NEW)  # Only interpret if() arguments as variables or keywords when unquoted
cmake_policy(SET CMP0042 NEW)  # MACOSX_RPATH is enabled by default
cmake_policy(SET CMP0063 NEW)  # Honor visibility properties for all target types
cmake_policy(SET CMP0077 NEW)  # option() honors normal variables
cmake_policy(SET CMP0120 NEW)  # The WriteCompilerDetectionHeader module is removed

#
# General CMake settings
# 
# NOTE: Switching to "Release" or "RelWithDebInfo" (instead of "Debug") often speeds up 
# both build times and runtime on resource-constrained devices like the Raspberry Pi.
# Additionally, you can invoke your build with "-j <n>" for parallel compilation 
# (e.g., `make -j4`).
#
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

#
# Try to use ccache if available (big speed up on repeated builds)
#
find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    message(STATUS "Using ccache for faster repeated builds on Raspberry Pi.")
    set(CMAKE_CXX_COMPILER_LAUNCHER "${CCACHE_PROGRAM}")
endif()

#
# Some optimized flags for Release on ARM-based systems (e.g., Pi 4 is armv7l or aarch64).
# Adjust these based on your Pi version if desired.
#
if(CMAKE_SYSTEM_PROCESSOR MATCHES "arm" OR CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64")
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -march=native -mtune=native")
endif()

#
# Optional color output for non-Windows platforms
#
if(NOT WIN32)
    string(ASCII 27 Esc)
    set(ColourReset "${Esc}[m")
    set(ColourBold  "${Esc}[1m")
    set(Red         "${Esc}[31m")
    set(Green       "${Esc}[32m")
    set(Yellow      "${Esc}[33m")
    set(Blue        "${Esc}[34m")
    set(Magenta     "${Esc}[35m")
    set(Cyan        "${Esc}[36m")
    set(White       "${Esc}[37m")
    set(BoldRed     "${Esc}[1;31m")
    set(BoldBlue    "${Esc}[1;90m")
    set(Reset       "${Esc}[0m")
endif()

#
# Add our custom CMake modules and register them
#
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(cmake/Custom.cmake)
include(GenerateExportHeader)
include(cmake/Coverage.cmake)
include(cmake/GenerateTemplateExportHeader.cmake)
include(cmake/GetGitRevisionDescription.cmake)
include(cmake/HealthCheck.cmake)
include(cmake/LibHackRf.cmake)
#
# Optionally include the WriteCompilerDetectionHeader if available in newer CMake
#
set(WriterCompilerDetectionHeaderFound NOTFOUND)
if(${CMAKE_VERSION} VERSION_GREATER "3.2")
    include(WriteCompilerDetectionHeader OPTIONAL RESULT_VARIABLE WriterCompilerDetectionHeaderFound)
endif()

#
# Gather Git revision
#
get_git_head_revision(GIT_REFSPEC GIT_SHA1)
string(SUBSTRING "${GIT_SHA1}" 0 12 GIT_REV)
if(NOT GIT_SHA1)
    set(GIT_REV "0")
endif()

#
# Get build date/time with milliseconds
#
if(WIN32)
    execute_process(
        COMMAND powershell -Command "[DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss.fff')"
        OUTPUT_VARIABLE BUILD_DATE
    )
else()
    execute_process(
        COMMAND bash -c "echo -n $(date '+%Y-%m-%d %H:%M:%S.%3N')"
        OUTPUT_VARIABLE BUILD_DATE
    )
endif()

add_definitions(-DBUILD_DATE="${BUILD_DATE}")

#
# Meta information
#
set(META_PROJECT_NAME        "ndrocketry")
set(META_PROJECT_DESCRIPTION "NDRocketry FRANC System")
set(META_AUTHOR_ORGANIZATION "University of Notre Dame")
set(META_AUTHOR_DOMAIN       "https://github.com/cginternals/")
set(META_AUTHOR_MAINTAINER   "ndrocketry@nd.edu")
set(META_VERSION_MAJOR       "1")
set(META_VERSION_MINOR       "0")
set(META_VERSION_PATCH       "0")
set(META_VERSION_REVISION    "${GIT_REV}")
set(META_VERSION             "${META_VERSION_MAJOR}.${META_VERSION_MINOR}.${META_VERSION_PATCH}")
set(META_NAME_VERSION        "${META_PROJECT_NAME} v${META_VERSION} (${META_VERSION_REVISION})")
set(META_CMAKE_INIT_SHA      "${GIT_REV}")

string(MAKE_C_IDENTIFIER ${META_PROJECT_NAME} META_PROJECT_ID)
string(TOUPPER ${META_PROJECT_ID} META_PROJECT_ID)

#
# Configure version.h
#
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/version.h.in
    ${CMAKE_CURRENT_BINARY_DIR}/version.h
)

#
# Template checks, linting, coverage
# (Note: disabling these can speed up builds, especially on a Pi.)
#
add_check_template_target(${META_CMAKE_INIT_SHA})
enable_cppcheck(ON)
enable_clang_tidy(ON)
# enable_coverage(${OPTION_ENABLE_COVERAGE})


#
# Add external libraries
#

# Quill
add_subdirectory(
    ${CMAKE_CURRENT_LIST_DIR}/lib/quill
)

# FlatBuffers
# add_subdirectory(
#     ${CMAKE_CURRENT_SOURCE_DIR}/lib/flatbuffers
#     ${CMAKE_BINARY_DIR}/flatbuffers-build
#     EXCLUDE_FROM_ALL
# )

# --- Option 1: Try to use pkg-config to find hackrf ---
find_package(PkgConfig)
if(PKG_CONFIG_FOUND)
  pkg_check_modules(HACKRF QUIET hackrf)
endif()

if(HACKRF_FOUND)
  message(STATUS "Found HackRF via pkg-config")
  include_directories(${HACKRF_INCLUDE_DIRS})
  link_directories(${HACKRF_LIBRARY_DIRS})
else()
  message(STATUS "HackRF not found via pkg-config. Falling back to find_library()/find_path()")

  # Search for the HackRF library in common locations
  find_library(HACKRF_LIBRARY
    NAMES hackrf
    PATHS /usr/lib /usr/local/lib
  )

  # Search for the hackrf.h header. Notice we include /usr/local/include/libhackrf.
  find_path(HACKRF_INCLUDE_DIR
    NAMES hackrf.h
    PATHS /usr/include /usr/local/include /usr/local/include/libhackrf
  )

  if(NOT HACKRF_LIBRARY)
    message(FATAL_ERROR "Could not find HackRF library. Please ensure libhackrf-dev is installed.")
  endif()

  if(NOT HACKRF_INCLUDE_DIR)
    message(FATAL_ERROR "Could not find HackRF headers. Please ensure libhackrf-dev is installed.")
  endif()

  message(STATUS "Found HackRF library: ${HACKRF_LIBRARY}")
  message(STATUS "Found HackRF include directory: ${HACKRF_INCLUDE_DIR}")
  include_directories(${HACKRF_INCLUDE_DIR})
endif()

if(NOT HACKRF_FOUND)
  set(HACKRF_LIBRARIES ${HACKRF_LIBRARY})
endif()

#
# Project-wide include directories
#
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_BINARY_DIR}
)



#
# Main executable
#
add_executable(${PROJECT_NAME}
    src/main.cpp
    src/aprs.cpp
    src/ax25.cpp
    src/dsp.cpp
    src/logger.cpp
    src/transmit.cpp
    src/config.cpp
    src/interconnect.cpp
)

#
# Set the runtime output directory
#
set_target_properties(${PROJECT_NAME} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)

#
# Include directories for this target
#
target_include_directories(${PROJECT_NAME}
    PRIVATE
        ${CMAKE_CURRENT_BINARY_DIR}         # for the generated version.h
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

#
# Link libraries
#
target_link_libraries(${PROJECT_NAME}
    PRIVATE
        quill::quill
        ${HACKRF_LIBRARIES}
)

#
# Compiler features and settings
#
target_compile_features(${PROJECT_NAME} PRIVATE cxx_std_17)

if(NOT MSVC)
    target_compile_options(${PROJECT_NAME} PRIVATE -Werror=return-type)
endif()

#
# Optional post-build script
#
add_custom_command(
    TARGET ${PROJECT_NAME}
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E env
            bash ${CMAKE_SOURCE_DIR}/scripts/post_build_script.sh
)
