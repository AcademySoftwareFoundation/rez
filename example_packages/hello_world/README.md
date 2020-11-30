Welcome to building your first rez package!

This package uses a simple python-based build script, and explicitly specifies
the build command using the `build_command` attribute in package.py.

Rez has extensible support for other build systems, and comes with CMake support
included. A *CMakeLists.txt.example* file is provided; to use cmake instead,
just ensure that the cmake binary is visible; rename *CMakeLists.txt.example* to
*CMakeLists.txt*; and remove the `build_command` attribute from package.py. Rez
then determines which build system to use based on the build file found in the
package source root.

When you run *rez-build -i*, rez uses your package's definition file (package.py)
to create the correct build environment, and then runs the appropriate build
system's executable within that environment.
