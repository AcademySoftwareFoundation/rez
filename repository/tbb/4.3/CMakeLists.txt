CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(RezRepository)
include(ExternalProject)

set(tbb_version $ENV{REZ_BUILD_PROJECT_VERSION})

rez_set_archive(
    url_tbb tbb/tbb-${tbb_version}.tgz
    https://www.threadingbuildingblocks.org/sites/default/files/software_releases/source/tbb43_20150611oss_src.tgz
)

ExternalProject_add(
    tbb
    URL ${url_tbb}
    PREFIX tbb
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ""
    INSTALL_COMMAND ""
    BUILD_IN_SOURCE 1
    BUILD_COMMAND make -j$ENV{REZ_BUILD_THREAD_COUNT} VERBOSE=1
)

ExternalProject_Get_Property(tbb SOURCE_DIR)

install(
    CODE
    # tbb doesn't have a 'make install' target, we have to provide it
    "execute_process(
        COMMAND python install.py ${SOURCE_DIR} ${CMAKE_INSTALL_PREFIX}
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    )"
)
