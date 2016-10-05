CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(RezRepository)
include(ExternalProject)

# ------------------------------------------------------------------------------
# python has been successfully built on:
#
# (1)
# Description:    Ubuntu 12.04.4 LTS
# LSB Version:    core-2.0-amd64:core-2.0-noarch:core-3.0-amd64:core-3.0-noarch:
#                 core-3.1-amd64:core-3.1-noarch:core-3.2-amd64:core-3.2-noarch:
#                 core-4.0-amd64:core-4.0-noarch
# With:
# apt-get install build-essential
# apt-get install libz-dev
# apt-get install libreadline-dev
# apt-get install libncursesw5-dev
# apt-get install libssl-dev
# apt-get install libgdbm-dev
# apt-get install libsqlite3-dev
# apt-get install libbz2-dev
# ------------------------------------------------------------------------------


set(python_version $ENV{REZ_BUILD_PROJECT_VERSION})

rez_set_archive(
    url_python python/Python-${python_version}.tgz
    http://www.python.org/ftp/python/${python_version}/Python-${python_version}.tgz
)

set(make_args -j$ENV{REZ_BUILD_THREAD_COUNT} VERBOSE=1)

if(${REZ_BUILD_INSTALL})
    set(install_cmd make install ${make_args})
else()
    set(install_cmd "")
endif()

ExternalProject_add(
    python
    URL ${url_python}
    PREFIX python
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ./configure --prefix=${CMAKE_INSTALL_PREFIX} --enable-shared --enable-ipv6 --enable-unicode=ucs4
    INSTALL_COMMAND "${install_cmd}"
    BUILD_IN_SOURCE 1
    BUILD_COMMAND make ${make_args}
)
