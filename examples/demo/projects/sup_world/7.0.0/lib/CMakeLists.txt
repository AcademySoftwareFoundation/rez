CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

# if we were using boost, you might see something like this
# set(boost_COMPONENTS thread system)

rez_find_packages(PREFIX pkgs AUTO)

# build and install lib
FILE(GLOB_RECURSE cpp_files "*.cpp")
add_library ( supworld STATIC ${cpp_files} )
TARGET_LINK_LIBRARIES(supworld ${pkgs_LIBRARIES})
INSTALL ( TARGETS supworld DESTINATION lib )

# install the headers
FILE(GLOB_RECURSE h_files "*.h")
rez_install_files(
	${h_files}
	DESTINATION include/supworld
)
