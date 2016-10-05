CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(RezRepository)
include(ExternalProject)

set(binutils_version $ENV{REZ_BUILD_PROJECT_VERSION})

rez_set_archive(
	url_binutils binutils/binutils-${binutils_version}.tar.gz
	http://ftp.gnu.org/gnu/binutils/binutils-${binutils_version}.tar.gz
)

set(make_args -j$ENV{REZ_BUILD_THREAD_COUNT} VERBOSE=1)

if(${REZ_BUILD_INSTALL})
    set(install_cmd make install ${make_args})
else()
    set(install_cmd "")
endif()

ExternalProject_add(
    binutils
    URL ${url_binutils}
    PREFIX binutils
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ./configure -prefix=${CMAKE_INSTALL_PREFIX} --disable-nls --disable-werror
    INSTALL_COMMAND "${install_cmd}"
    BUILD_IN_SOURCE 1
    BUILD_COMMAND make ${make_args}
)
