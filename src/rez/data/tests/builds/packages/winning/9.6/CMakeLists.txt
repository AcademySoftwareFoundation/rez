cmake_minimum_required(VERSION 2.8)

# On Linux defining a project name is usually not necessary for rez packages which simply use cmake
# as a Makefile recipe generator, however to be cross-compatible with Windows we can define it to
# get the same functionality.
#
# Here we are telling cmake this is not a compiled project by providing NONE for the second argument.
#
# The project function is only being used in this in case because we are on Windows and want to use
# the gnu make utility provided by a `make` rez package or configuring a path to `make.exe` in rez config.
# This bypasses having to use the default `nmake` on Windows which requires the Windows compiler and
# linker and attempts to build a simple c++ executable during a build.
#
project($ENV{REZ_BUILD_PROJECT_NAME}, NONE)

include(RezBuild)

file(GLOB_RECURSE py_files "python/*.py")

# Not using rez_install_python b/c we don't want to require python for this test package
rez_install_files(
    ${py_files}
    DESTINATION .
)
