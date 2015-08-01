CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(RezRepository)
include(ExternalProject)

# ------------------------------------------------------------------------------
# gcc has been successfully built on:
#
# (1)
# Description:    Ubuntu 12.04.4 LTS
# LSB Version:    core-2.0-amd64:core-2.0-noarch:core-3.0-amd64:core-3.0-noarch:
#                 core-3.1-amd64:core-3.1-noarch:core-3.2-amd64:core-3.2-noarch:
#                 core-4.0-amd64:core-4.0-noarch
# ------------------------------------------------------------------------------


set(gmp_version 4.3.2)
set(mpfr_version 2.4.2)
set(mpc_version 0.8.1)
set(gcc_version $ENV{REZ_BUILD_PROJECT_VERSION})

rez_set_archive(
	url_gmp gcc/gmp-${gmp_version}.tar.bz2
	http://ftp.gnu.org/gnu/gmp/gmp-${gmp_version}.tar.bz2
)
rez_set_archive(
	url_mpfr gcc/mpfr-${mpfr_version}.tar.bz2
	http://www.mpfr.org/mpfr-current/mpfr-${mpfr_version}.tar.bz2
)
rez_set_archive(
	url_mpc gcc/mpc-${mpc_version}.tar.gz
	http://ftp.gnu.org/gnu/mpc/mpc-${mpc_version}.tar.gz
)
rez_set_archive(
	url_gcc gcc/gcc-${gcc_version}.tar.bz2
	ftp://ftp.gnu.org/gnu/gcc/gcc-${gcc_version}/gcc-${gcc_version}.tar.bz2
)

add_custom_target(
    build_gcc
    ALL
    COMMAND bash ./build.sh ${CMAKE_BINARY_DIR} ${CMAKE_INSTALL_PREFIX} $ENV{REZ_REPO_PAYLOAD_DIR} ${gcc_version} ${gmp_version} ${mpfr_version} ${mpc_version}
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    VERBATIM
)

install(
    CODE
    "execute_process(
        COMMAND make install
        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/objdir
    )"
)
