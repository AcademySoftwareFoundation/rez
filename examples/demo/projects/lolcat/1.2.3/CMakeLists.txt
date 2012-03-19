CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

rez_find_packages(PREFIX pkgs AUTO)

# here we are passing a define through to the compiler so that #ifdefs can be used to
# change the code depending on the version of translate_lib in use. Note that rez-build
# automatically creates the following (and will do so for every package in use):
# TRANSLATE_LIB_VERSION
# TRANSLATE_LIB_MAJOR_VERSION
# TRANSLATE_LIB_MINOR_VERSION
# TRANSLATE_LIB_PATCH_VERSION
ADD_DEFINITIONS(-DTRANSLATE_VER=${TRANSLATE_LIB_VERSION})
ADD_DEFINITIONS(-DTRANSLATE_MAJOR_VER=${TRANSLATE_LIB_MAJOR_VERSION})
ADD_DEFINITIONS(-DTRANSLATE_MINOR_VER=${TRANSLATE_LIB_MINOR_VERSION})

ADD_EXECUTABLE (test_lolcat main.cpp)

TARGET_LINK_LIBRARIES ( test_lolcat ${pkgs_LIBRARIES} )

INSTALL ( TARGETS test_lolcat DESTINATION bin )
