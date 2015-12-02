CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(RezRepository)
include(ExternalProject)


set(version $ENV{REZ_BUILD_PROJECT_VERSION})

if(NOT ${REZ_BUILD_INSTALL})
    message(FATAL_ERROR "Must install this package with -i flag")
endif()

rez_set_archive(
    url pip/pip-${version}.tar.gz
    https://github.com/pypa/pip/archive/7.1.2.tar.gz
)

set(src_path ${CMAKE_BINARY_DIR}/pip/src/pip)

if(${CMAKE_SYSTEM_NAME} MATCHES "Linux")
    set(install_cmd bash ${CMAKE_SOURCE_DIR}/install.sh ${src_path} ${CMAKE_INSTALL_PREFIX})
endif()

ExternalProject_add(
    pip
    URL ${url}
    PREFIX pip
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ""
    BUILD_IN_SOURCE 1
    BUILD_COMMAND ""
    INSTALL_COMMAND "${install_cmd}"
)
