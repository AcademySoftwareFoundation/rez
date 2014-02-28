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

if(NOT DEFINED ENV{REZ_RELEASE_PACKAGES_PATH})
	message(FATAL_ERROR "REZ_RELEASE_PACKAGES_PATH was not defined in the environment.")
endif(NOT DEFINED ENV{REZ_RELEASE_PACKAGES_PATH})

if(NOT DEFINED ENV{REZ_BUILD_PROJECT_VERSION})
	message(FATAL_ERROR "REZ_BUILD_PROJECT_VERSION was not defined in the environment.")
endif(NOT DEFINED ENV{REZ_BUILD_PROJECT_VERSION})

if(NOT DEFINED ENV{REZ_BUILD_PROJECT_NAME})
	message(FATAL_ERROR "REZ_BUILD_PROJECT_NAME was not defined in the environment.")
endif(NOT DEFINED ENV{REZ_BUILD_PROJECT_NAME})

set(REZ_RELEASE_PACKAGES_PATH $ENV{REZ_RELEASE_PACKAGES_PATH})
set(REZ_BUILD_PROJECT_VERSION $ENV{REZ_BUILD_PROJECT_VERSION})
set(REZ_BUILD_PROJECT_NAME $ENV{REZ_BUILD_PROJECT_NAME})

# list of all packages used by this build
set(REZ_BUILD_ALL_PKGS "$ENV{REZ_BUILD_REQUIRES_UNVERSIONED} $ENV{REZ_BUILD_VARIANT_UNVERSIONED}")
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


# TODO Deprecate, this is very very old
# convert pkg-config search path, if it exists, into a cmake list for further consumption
#set(PKG_CONFIG_PATH_LIST)
#set(ENV_PKG_CONFIG_PATH $ENV{PKG_CONFIG_PATH})
#if(ENV_PKG_CONFIG_PATH)
#	string(REPLACE ":" ";" PKG_CONFIG_PATH_LIST ${ENV_PKG_CONFIG_PATH})
#endif(ENV_PKG_CONFIG_PATH)


#############################################################################
# include rez-build- related cmake modules
#############################################################################

include(Utils)
include(RezProject)
include(InstallFiles)
include(InstallDirs)
include(RezInstallCMake)
include(RezFindPackages)
include(RezInstallPython)
include(RezInstallDoxygen)


#############################################################################
# installation setup
#############################################################################

#
# determine package install directory (rez-cmake arg 'CENTRAL' will install
# centrally, otherwise packages always go to ~/packages). Typically however,
# central installs are done via rez-release.
#
if(CENTRAL)
	set(CMAKE_INSTALL_PREFIX ${REZ_RELEASE_PACKAGES_PATH})
	set(REZ_FILE_INSTALL_PERMISSIONS OWNER_READ GROUP_READ WORLD_READ)
else(CENTRAL)
	set(CMAKE_INSTALL_PREFIX $ENV{REZ_LOCAL_PACKAGES_PATH})
	set(REZ_FILE_INSTALL_PERMISSIONS OWNER_READ GROUP_READ WORLD_READ OWNER_WRITE GROUP_WRITE WORLD_WRITE)
endif(CENTRAL)

set( CMAKE_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX}/${REZ_BUILD_PROJECT_NAME}/${REZ_BUILD_PROJECT_VERSION}/$ENV{REZ_BUILD_VARIANT_SUBDIR} )

set( REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS} OWNER_EXECUTE GROUP_EXECUTE WORLD_EXECUTE )


#############################################################################
# Automatic build and install actions
#############################################################################

rez_project()

#
# package.yaml is installed into the base path (ie not under variant subdirs).
#

set(PYAML_REL_DIR .)
set(varlist $ENV{REZ_BUILD_VARIANT_UNVERSIONED})
separate_arguments(varlist)

foreach(var ${varlist})
	set(PYAML_REL_DIR "../${PYAML_REL_DIR}")
endforeach(var ${varlist})
install( FILES
		./package.yaml
		DESTINATION ${PYAML_REL_DIR}
		PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS} )


#
# install the meta files. rez-build generates them, and
# they should always be present when invoking cmake/make
#

install( FILES
		${CMAKE_CURRENT_BINARY_DIR}/build-env.context
		${CMAKE_CURRENT_BINARY_DIR}/build-env.actual
		DESTINATION .metadata
		PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS} )

install( FILES
		${CMAKE_CURRENT_BINARY_DIR}/info.txt
		${CMAKE_CURRENT_BINARY_DIR}/changelog.txt
		DESTINATION ${PYAML_REL_DIR}/.metadata
		PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS} )


#
# 'build' the package.yaml, this is just here so that a project that doesn't actually build
# anything (like a production package for a show) still builds under rez-build.
#

add_custom_command(
	OUTPUT package.yaml
	COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_CURRENT_SOURCE_DIR}/package.yaml package.yaml
	COMMENT "Building package.yaml"
	DEPENDS package.yaml
	VERBATIM
)

add_custom_target ( package-yaml ALL DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/package.yaml )


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























#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
