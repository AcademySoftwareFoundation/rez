CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(ExternalProject)


set(gmp_version 4.3.2)
set(mpfr_version 2.4.2)
set(mpc_version 0.8.1)
set(gcc_version $ENV{REZ_BUILD_PROJECT_VERSION})

set(url_base $ENV{REZ_REPO_PAYLOAD_DIR}/gcc)
set(url_gmp ${url_base}/gmp-${gmp_version}.tar.bz2)
set(url_mpfr ${url_base}/mpfr-${mpfr_version}.tar.bz2)
set(url_mpc ${url_base}/mpc-${mpc_version}.tar.gz)
set(url_gcc ${url_base}/gcc-${gcc_version}.tar.bz2)

add_custom_target(
    build_gcc
    ALL
    COMMAND bash ./build.sh ${CMAKE_BINARY_DIR} ${CMAKE_INSTALL_PREFIX} ${url_base} ${gcc_version} ${gmp_version} ${mpfr_version} ${mpc_version}
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    VERBATIM
)
