CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(ExternalProject)


set(tbb_version $ENV{REZ_BUILD_PROJECT_VERSION})
set(url_base $ENV{REZ_REPO_PAYLOAD_DIR}/tbb)
set(url_tbb ${url_base}/tbb-${tbb_version}.tgz)

if(${REZ_BUILD_INSTALL})
    set(install_cmd make --directory ${CMAKE_BINARY_DIR} install_tbb)
else()
    set(install_cmd "")
endif()

ExternalProject_add(
    tbb
    URL ${url_tbb}
    PREFIX tbb
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ""
    INSTALL_COMMAND "${install_cmd}"
    BUILD_IN_SOURCE 1
    BUILD_COMMAND make VERBOSE=1
)

ExternalProject_Get_Property(tbb SOURCE_DIR)

# tbb doesn't have a 'make install' target, we have to provide it
add_custom_target(
    install_tbb
    COMMENT "Installing tbb..."
    COMMAND python install.py ${SOURCE_DIR} ${CMAKE_INSTALL_PREFIX}
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    VERBATIM
)
