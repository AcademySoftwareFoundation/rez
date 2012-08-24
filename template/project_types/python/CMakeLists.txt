cmake_minimum_required(VERSION 2.8)

include(RezBuild)
include(RezInstallDoxygen)

%(BIN_CMAKE_CODE)s

file(GLOB_RECURSE py_files "python/*.py")
rez_install_python(
    py
	FILES ${py_files}
	DESTINATION .
)


file(GLOB_RECURSE doc_files "docs/*")

rez_install_doxygen(
	doc
	FILES ${py_files} ${doc_files}
	DESTINATION doc
	DOXYPY

	# remove this once your docs have stabilised, then they will only be built and 
	# installed when you're performing a central install (ie a rez-release).
	FORCE 
)
