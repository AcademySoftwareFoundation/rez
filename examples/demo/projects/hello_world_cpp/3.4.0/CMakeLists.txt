CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)


rez_find_packages(PREFIX pkgs AUTO)

ADD_EXECUTABLE (test_hello_world_cpp main.cpp)

TARGET_LINK_LIBRARIES ( test_hello_world_cpp ${pkgs_LIBRARIES} )

INSTALL ( TARGETS test_hello_world_cpp DESTINATION bin )
