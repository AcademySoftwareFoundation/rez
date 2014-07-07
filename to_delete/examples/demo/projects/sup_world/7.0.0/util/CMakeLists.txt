CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

rez_find_packages(PREFIX pkgs AUTO)

# expose local lib
INCLUDE_DIRECTORIES ( ../lib )
LINK_DIRECTORIES( lib )

# build and install executable
ADD_EXECUTABLE (test_ghetto main.cpp)
TARGET_LINK_LIBRARIES ( test_ghetto supworld ${pkgs_LIBRARIES} )
INSTALL ( TARGETS test_ghetto DESTINATION bin )
