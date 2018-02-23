#
# This module should be included for projects built within a rez-build context. Several macros are made
# available (see those cmake filse for details): rez_find_packages, rez_install_cmake and rez_install_python.
#
# Including this file will implicitly call the cmake function project(<package_name>) for you.
#
# Output variables:
#
# For the current package, and each package in the current build variant:
# <PKG>_VERSION
# <PKG>_MAJOR_VERSION
# <PKG>_MINOR_VERSION
# <PKG>_PATCH_VERSION
#

#############################################################################
# make sure we're within a rez-build context
#############################################################################

if(NOT DEFINED ENV{REZ_BUILD_ENV})
	message(FATAL_ERROR "This project must be built with rez-build.")
endif(NOT DEFINED ENV{REZ_BUILD_ENV})

set(REZ_BUILD_ENV $ENV{REZ_BUILD_ENV})


#############################################################################
# setup rez-build system variables
#############################################################################

if(NOT DEFINED ENV{REZ_BUILD_PROJECT_VERSION})
	message(FATAL_ERROR "REZ_BUILD_PROJECT_VERSION was not defined in the environment.")
endif(NOT DEFINED ENV{REZ_BUILD_PROJECT_VERSION})

if(NOT DEFINED ENV{REZ_BUILD_PROJECT_NAME})
	message(FATAL_ERROR "REZ_BUILD_PROJECT_NAME was not defined in the environment.")
endif(NOT DEFINED ENV{REZ_BUILD_PROJECT_NAME})

set(REZ_BUILD_PROJECT_VERSION $ENV{REZ_BUILD_PROJECT_VERSION})
set(REZ_BUILD_PROJECT_NAME $ENV{REZ_BUILD_PROJECT_NAME})

# list of all packages used by this build
set(REZ_BUILD_ALL_PKGS "$ENV{REZ_BUILD_REQUIRES_UNVERSIONED}")
separate_arguments(REZ_BUILD_ALL_PKGS)

# move all package versions into <pkg>_VERSION variables so client CMakeLists.txt can use them.
# also generates <pkg>_MAJOR_VERSION etc variables, in case they are needed.
foreach(pkg ${REZ_BUILD_ALL_PKGS})
	string(TOUPPER ${pkg} upkg)
	set(${upkg}_VERSION $ENV{REZ_${upkg}_VERSION})
	if(${upkg}_VERSION)
		string(REGEX REPLACE "\\." ";" vercomps "${${upkg}_VERSION};0;0")
		list(GET vercomps "0" ${upkg}_MAJOR_VERSION)
		list(GET vercomps "1" ${upkg}_MINOR_VERSION)
		list(GET vercomps "2" ${upkg}_PATCH_VERSION)
	endif(${upkg}_VERSION)
endforeach(pkg ${REZ_BUILD_ALL_PKGS})

if(REZ_BUILD_PROJECT_VERSION)
	string(TOUPPER ${REZ_BUILD_PROJECT_NAME} upkg)
	set(${upkg}_VERSION ${REZ_BUILD_PROJECT_VERSION})
	string(REGEX REPLACE "\\." ";" vercomps "${${upkg}_VERSION};0;0")
	list(GET vercomps "0" ${upkg}_MAJOR_VERSION)
	list(GET vercomps "1" ${upkg}_MINOR_VERSION)
	list(GET vercomps "2" ${upkg}_PATCH_VERSION)
endif(REZ_BUILD_PROJECT_VERSION)


#############################################################################
# include rez-build- related cmake modules
#############################################################################

include(Colorize)
include(Utils)
include(RezProject)
include(InstallFiles)
include(InstallDirs)
include(RezInstallCMake)
include(RezFindPackages)
include(RezInstallPython)
#include(RezInstallDoxygen)


#############################################################################
# installation setup
#############################################################################

set( REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS} OWNER_EXECUTE GROUP_EXECUTE WORLD_EXECUTE OWNER_READ GROUP_READ WORLD_READ )


#############################################################################
# Automatic build and install actions
#############################################################################

rez_project()

#
# Set C++ Cflags/LDflags based on rez-cmake flags such as -o
#

if(COVERAGE)
	ADD_DEFINITIONS(-pg -fprofile-arcs -ftest-coverage)
	SET_GLOBAL_LINKER_CXX_FLAGS(-fprofile-arcs)
endif(COVERAGE)


#############################################################################
# utility macros
#############################################################################

# This macro sets the variable named by result equal to TRUE if 'pkg_string' is
# the unversioned name of any package being used in the current build variant.
macro(rez_package_in_use pkg_string result)
	list_contains(${result} ${pkg_string} ${REZ_BUILD_ALL_PKGS})
endmacro(rez_package_in_use pkg_string result)
