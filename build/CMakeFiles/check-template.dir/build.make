# CMAKE generated file: DO NOT EDIT!
# Generated by "Unix Makefiles" Generator, CMake Version 3.25

# Delete rule output on recipe failure.
.DELETE_ON_ERROR:

#=============================================================================
# Special targets provided by cmake.

# Disable implicit rules so canonical targets will work.
.SUFFIXES:

# Disable VCS-based implicit rules.
% : %,v

# Disable VCS-based implicit rules.
% : RCS/%

# Disable VCS-based implicit rules.
% : RCS/%,v

# Disable VCS-based implicit rules.
% : SCCS/s.%

# Disable VCS-based implicit rules.
% : s.%

.SUFFIXES: .hpux_make_needs_suffix_list

# Command-line flag to silence nested $(MAKE).
$(VERBOSE)MAKESILENT = -s

#Suppress display of executed commands.
$(VERBOSE).SILENT:

# A target that is always out of date.
cmake_force:
.PHONY : cmake_force

#=============================================================================
# Set environment variables for the build.

# The shell in which to execute make rules.
SHELL = /bin/sh

# The CMake executable.
CMAKE_COMMAND = /usr/bin/cmake

# The command to remove a file.
RM = /usr/bin/cmake -E rm -f

# Escaping for special characters.
EQUALS = =

# The top-level source directory on which CMake was run.
CMAKE_SOURCE_DIR = /local/rocketry/rocketry-24-25

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /local/rocketry/rocketry-24-25/build

# Utility rule file for check-template.

# Include any custom commands dependencies for this target.
include CMakeFiles/check-template.dir/compiler_depend.make

# Include the progress variables for this target.
include CMakeFiles/check-template.dir/progress.make

CMakeFiles/check-template:
	/usr/bin/cmake -DPROJECT_SOURCE_DIR= -DPROJECT_BINARY_DIR= -DAPPLIED_CMAKE_INIT_SHA=0f16d56f494a -P /cmake/CheckTemplate.cmake

check-template: CMakeFiles/check-template
check-template: CMakeFiles/check-template.dir/build.make
.PHONY : check-template

# Rule to build all files generated by this target.
CMakeFiles/check-template.dir/build: check-template
.PHONY : CMakeFiles/check-template.dir/build

CMakeFiles/check-template.dir/clean:
	$(CMAKE_COMMAND) -P CMakeFiles/check-template.dir/cmake_clean.cmake
.PHONY : CMakeFiles/check-template.dir/clean

CMakeFiles/check-template.dir/depend:
	cd /local/rocketry/rocketry-24-25/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /local/rocketry/rocketry-24-25 /local/rocketry/rocketry-24-25 /local/rocketry/rocketry-24-25/build /local/rocketry/rocketry-24-25/build /local/rocketry/rocketry-24-25/build/CMakeFiles/check-template.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : CMakeFiles/check-template.dir/depend
