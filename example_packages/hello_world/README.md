Welcome to building your first rez package!

This package gets built using 'bez', a very simple python-based build system that
comes with rez. It reads the *rezbuild.py* file, and executes the *build* function
within, passing in build info such as *source_path* and *install_path*.

Rez has extensible support for other build systems, and comes with CMake support
included. A *CMakeLists.txt.example* file is provided; to use cmake instead,
just ensure that the cmake binary is visible; rename *CMakeLists.txt.example* to
*CMakeLists.txt*; and delete or rename *rezbuild.py*. Rez determines which build
system to use based on the build file found in the package source root.

When you run *rez-build -i*, rez uses your package's definition file (package.py)
to create the correct build environment, and then runs the appropriate build
system's executable within that environment.
