#!/bin/bash

# -------------------------------------------------------------------
# Script Name: generate_flatbuffers.sh
# Description: Generates FlatBuffers Python classes from a schema
#              and organizes them into the specified target directory.
# -------------------------------------------------------------------

# Exit immediately if a command exits with a non-zero status
set -e

# ---------------------------- Configuration ------------------------

# Name of your FlatBuffers schema file
SCHEMA_FILE="sensors.fbs"

# Target directory where the generated Python code will be placed
TARGET_DIR="/local/franc/franc-master-control/src/lib"

# Temporary directory for FlatBuffers code generation
TEMP_OUTPUT_DIR="flatbuffers_generated"

# Desired name for the Python module/folder
MODULE_NAME="sensor_log"

# ------------------------- Helper Functions -------------------------

# Function to print error messages and exit
function error_exit {
    echo -e "\\033[0;31mError: $1\\033[0m" >&2
    exit 1
}

# Function to print success messages
function success_msg {
    echo -e "\\033[0;32m$1\\033[0m"
}

# -------------------------- Script Logic ----------------------------

# 1. Check for FlatBuffers Compiler (`flatc`)
if ! command -v flatc &> /dev/null
then
    error_exit "FlatBuffers compiler 'flatc' is not installed or not in PATH. Please install it from https://github.com/google/flatbuffers/releases and ensure it's accessible."
fi

# 2. Verify Schema File Exists
if [ ! -f "$SCHEMA_FILE" ]; then
    error_exit "Schema file '$SCHEMA_FILE' not found in the current directory ($(pwd)). Please ensure the schema file exists."
fi

# 3. Create Temporary Output Directory
if [ -d "$TEMP_OUTPUT_DIR" ]; then
    echo "Removing existing temporary directory '$TEMP_OUTPUT_DIR'..."
    rm -rf "$TEMP_OUTPUT_DIR"
fi
mkdir "$TEMP_OUTPUT_DIR"

# 4. Generate Python Code Using `flatc`
echo "Generating Python classes from '$SCHEMA_FILE'..."
flatc --python "$SCHEMA_FILE"
mv SensorLog/ flatbuffers_generated/

# 5. Verify Generation Success
GENERATED_FOLDER="$TEMP_OUTPUT_DIR/SensorLog"
if [ ! -d "$GENERATED_FOLDER" ]; then
    error_exit "Failed to generate Python classes. Expected directory '$GENERATED_FOLDER' not found."
fi

# 6. Prepare Target Directory
if [ ! -d "$TARGET_DIR" ]; then
    echo "Target directory '$TARGET_DIR' does not exist. Creating it..."
    mkdir -p "$TARGET_DIR"
fi

# 7. Remove Existing Module in Target Directory (If Any)
if [ -d "$TARGET_DIR/$MODULE_NAME" ]; then
    echo "Removing existing module directory '$TARGET_DIR/$MODULE_NAME'..."
    rm -rf "$TARGET_DIR/$MODULE_NAME"
fi

# 8. Move and Rename Generated Code to Target Directory
echo "Moving generated Python classes to '$TARGET_DIR/$MODULE_NAME'..."
mv "$GENERATED_FOLDER" "$TARGET_DIR/$MODULE_NAME"

# 9. Clean Up Temporary Directory
echo "Cleaning up temporary directory '$TEMP_OUTPUT_DIR'..."
rm -rf "$TEMP_OUTPUT_DIR"

# 10. Confirmation Message
success_msg "FlatBuffers Python classes have been successfully generated and placed in '$TARGET_DIR/$MODULE_NAME'."

# ------------------------------ End -----------------------------------
