CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

rez_find_packages(PREFIX pkgs AUTO)

set(REZ_BUILD_DIR ${CMAKE_BINARY_DIR}/rez-external)
file(MAKE_DIRECTORY ${REZ_BUILD_DIR})

# copy CMAKE_INSTALL_PREFIX to a rez variable for future proofing
set(REZ_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX})

set(REZ_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/%(source_dir)s)
set(REZ_SOURCE_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/%(source_root)s)

%(extra_cmake_commands)s

add_custom_target(
  %(target_commands)s
  WORKING_DIRECTORY %(working_dir)s
)

# Create Cmake file
rez_install_cmake(AUTO)
