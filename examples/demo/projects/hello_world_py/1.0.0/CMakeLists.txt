CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

FILE(GLOB_RECURSE py_files "src/*.py")

rez_install_python(py
	FILES ${py_files}
	RELATIVE src
	DESTINATION py/hello_world
)


rez_install_files(
	bin/test_hello_world_py
	DESTINATION .
	EXECUTABLE
)
