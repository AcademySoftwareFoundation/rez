CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

rez_find_packages(PREFIX pkgs AUTO)

ADD_EXECUTABLE (test_translated_hello_world main.cpp)

TARGET_LINK_LIBRARIES ( test_translated_hello_world ${pkgs_LIBRARIES} )

INSTALL ( TARGETS test_translated_hello_world DESTINATION bin )
