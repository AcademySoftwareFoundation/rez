CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

# either one of these will work...
include(buildTools_toupper)
#rez_find_packages(PREFIX pkgs AUTO)

FILE(GLOB_RECURSE txt_files "data/*.txt")

install_uppercase(
	myupper
	FILES ${txt_files}
	RELATIVE data
	DESTINATION .
)
