cmake_minimum_required(VERSION 2.8)

# You must include this line
include(RezBuild)

# This recursively finds all .py files under the 'python' dir, and stores them
# into the list variable 'py_files'. Note that the path structure is retained -
# for example one entry here will be 'python/greetings.py'.
file(GLOB_RECURSE py_files "python/*.py")

# This installs a list of python files into the given directory, which is
# relative to the installation path. Each file is compiled to make sure there
# are no syntax errors (note though that the source is not executed).
rez_install_python(
    py
    FILES ${py_files}
    DESTINATION .
)

# This finds all files directly in the 'bin' dir.
file(GLOB bin_files "bin/*")

# This installs the bin files, and updates their permissions to executable.
rez_install_files(
    ${bin_files}
    DESTINATION .
    EXECUTABLE
)
