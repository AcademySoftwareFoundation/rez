CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

rez_find_packages(PREFIX pkgs AUTO)

# build/install lib
FILE(GLOB_RECURSE cpp_files "src/*.cpp")
add_library ( translate SHARED ${cpp_files} )
TARGET_LINK_LIBRARIES(translate ${pkgs_LIBRARIES})
INSTALL ( TARGETS translate DESTINATION lib )

# install headers
FILE(GLOB_RECURSE h_files "src/*.h")
rez_install_files(
	${h_files}
	RELATIVE src
	DESTINATION include/translate
)

# install cmake file
rez_install_cmake(
	DESTINATION 	cmake
	INCLUDE_DIRS	include 	${pkgs_INCLUDE_DIRS}
	LIBRARY_DIRS 	lib 		${pkgs_LIBRARY_DIRS}
	LIBRARIES		translate	${pkgs_LIBRARIES}
	DEFINITIONS					${pkgs_DEFINITIONS}
)
