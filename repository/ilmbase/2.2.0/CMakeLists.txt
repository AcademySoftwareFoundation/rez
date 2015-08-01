CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(RezRepository)
include(ExternalProject)


set(ilmbase_version $ENV{REZ_BUILD_PROJECT_VERSION})

rez_set_archive(
    url_ilmbase ilmbase/ilmbase-${ilmbase_version}.tar.gz
    http://download.savannah.nongnu.org/releases/openexr/ilmbase-${ilmbase_version}.tar.gz
)

if(${REZ_BUILD_INSTALL})
    set(install_cmd make install)
else()
    set(install_cmd "")
endif()

ExternalProject_add(
    ilmbase
    URL ${url_ilmbase}
    PREFIX ilmbase
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ./configure --prefix=${CMAKE_INSTALL_PREFIX} --with-pic --disable-debug --enable-shared=no
    INSTALL_COMMAND "${install_cmd}"
    BUILD_IN_SOURCE 1
    BUILD_COMMAND make -j8 VERBOSE=1
)
