#
# macro:
# rez_find_packages
#
# ------------------------------
# Overview
# ------------------------------
#
# usage:
# find_rez_package([package1 package2 .. packageN] [PREFIX prefix] [REQUIRED] [AUTO])
# where 'packageN' is an UNVERSIONED package name (eg 'boost')
#
# This macro attempts to find the listed packages, and combines the resulting cflags and
# ldflags into output variables. If no packages are listed, then all packages used by the
# current build variant is implied. If AUTO is specified, then include dirs, library dirs
# and definitions (extra cflags) are automatically set via cmake native functions
# include_directories(), link_directories(), add_definitions().
#
# INCLUDE_DIRS_NO_SYSTEM can be set to disable the declaration of INCLUDE_DIRS
# as SYSTEM.
#
# ------------------------------
# Finding a Package
# ------------------------------
#
# For each package, we first attempt to include the file <package>.cmake. If this file does not
# exist, then we attempt to invoke 'pkg-config <package>'. If the package does not have a .pc
# file, then we silently skip this package, unless REQUIRES is specified, in which case an
# error results. Packages expose their cmake modules/pc files by providing commands in their
# package.yamls which append to CMAKE_MODULE_PATH/PKG_CONFIG_PATH appropriately.
#
# If a package provides a cmake module, then the module must return these variables:
# <package>_INCLUDE_DIRS, <package>_LIBRARY_DIRS, <package>_LIBRARIES, <package>_DEFINITIONS
#
# If a package provides a .pc file, then the relevant output vars are generated automatically.
#
# ------------------------------
# Components
# ------------------------------
#
# It is common for a package to provide 'components' to use, usually these represent separate
# libraries within the package that can be optionally linked to. Package cmake modules should
# expect the input variable <package>_COMPONENTS to list the desired components, if any, and
# should take appropriate action.
#
# In the case of packages that provide .pc files, they are expected to provide
# <package>_<component>.pc files for each provided component, as well as a base <package>.pc as
# usual.
#
# ------------------------------
# Static Linking
# ------------------------------
#
# Package libraries are assumed to be linked dynamically by default. To enable static linking
# of a package, the input variable <package>_STATIC is expected, and is usually set to ON or
# OFF. Packages' cmake modules should expect this variable if they support static linking. For
# packages with .pc files, ### TODO THIS IS DIFFICULT AND THERE IS NO NATIVE SUPPORT :( ###
#
# ------------------------------
# Return Values
# ------------------------------
#
# Each packages' output variables are combined into the following variables:
# <PREFIX>_INCLUDE_DIRS
# <PREFIX>_SYSTEM_INCLUDE_DIRS
# <PREFIX>_LIBRARY_DIRS
# <PREFIX>_LIBRARIES
# <PREFIX>_DEFINITIONS
#
# ------------------------------
# Notes
# ------------------------------
#
# - debug/release not thought about yet
# - static/dynamic linking not thought about on pkgconfig files support yet
#

include(Utils)
include(FindPkgConfig)
include(FindStaticLibs)

if(NOT REZ_BUILD_ENV)
	message(FATAL_ERROR "Include RezBuild, not this cmake module directly.")
endif(NOT REZ_BUILD_ENV)


macro (rez_find_packages)

	message("")
	message("rez_find_packages: in ${CMAKE_CURRENT_SOURCE_DIR}")
	message("----------------------------------------------------------------")

	# parse args
	#--------------------------------------------------------------------

	parse_arguments(DFP "PREFIX" "REQUIRED;AUTO;INCLUDE_DIRS_NO_SYSTEM" ${ARGN})

	list(GET DFP_PREFIX 0 DFP_PREFIX)
	if(NOT DFP_PREFIX)
		message(FATAL_ERROR "need to specify PREFIX in call to rez_find_packages")
	endif(NOT DFP_PREFIX)

	# no pkgs listed means use all packages
	if(NOT DFP_DEFAULT_ARGS)
		set(DFP_DEFAULT_ARGS ${REZ_BUILD_ALL_PKGS})
	endif(NOT DFP_DEFAULT_ARGS)

	set(${DFP_PREFIX}_INCLUDE_DIRS)
    set(${DFP_PREFIX}_SYSTEM_INCLUDE_DIRS)
	set(${DFP_PREFIX}_LIBRARY_DIRS)
	set(${DFP_PREFIX}_LIBRARIES)
	set(${DFP_PREFIX}_DEFINITIONS)


	# iterate over packages
	#--------------------------------------------------------------------
	foreach(pkg ${DFP_DEFAULT_ARGS})

	# note: this happens to work because CMAKE_MODULE_PATH is semicolon-delimited,
	# it is just coincidence that cmake will read this as being a list
	find_file(cmod_${pkg} ${pkg}.cmake $ENV{CMAKE_MODULE_PATH})

	if(cmod_${pkg})

		# cmake module found
		# ----------------------

		# pull in the module, this should define the pkg_XXX output vars
		include(${pkg})
		message("${Green}rez_find_packages: included ${BoldGreen}${pkg}.cmake${ColourReset}")

		if(${pkg}_INCLUDE_DIRS)
            if(${pkg}_USE_SYSTEM_INCLUDE_DIRS AND NOT DFP_INCLUDE_DIRS_NO_SYSTEM)
                list(APPEND ${DFP_PREFIX}_SYSTEM_INCLUDE_DIRS   ${${pkg}_INCLUDE_DIRS})
                message("    include dirs: ${${pkg}_INCLUDE_DIRS} ${Yellow}(SYSTEM)${ColourReset}")
            else(${pkg}_USE_SYSTEM_INCLUDE_DIRS)
                list(APPEND ${DFP_PREFIX}_INCLUDE_DIRS  ${${pkg}_INCLUDE_DIRS})
                message("    include dirs: ${${pkg}_INCLUDE_DIRS}")
            endif(${pkg}_USE_SYSTEM_INCLUDE_DIRS)
		endif(${pkg}_INCLUDE_DIRS)
		if(${pkg}_LIBRARY_DIRS)
			message("    library dirs: ${${pkg}_LIBRARY_DIRS}")
			list(APPEND ${DFP_PREFIX}_LIBRARY_DIRS 	${${pkg}_LIBRARY_DIRS})
		endif(${pkg}_LIBRARY_DIRS)
		if(${pkg}_LIBRARIES)
			message("    libraries:    ${${pkg}_LIBRARIES}")
			list(APPEND ${DFP_PREFIX}_LIBRARIES 	${${pkg}_LIBRARIES})
		endif(${pkg}_LIBRARIES)
		if(${pkg}_DEFINITIONS)
			message("    definitions:  ${${pkg}_DEFINITIONS}")
			list(APPEND ${DFP_PREFIX}_DEFINITIONS 	${${pkg}_DEFINITIONS})
		endif(${pkg}_DEFINITIONS)

	else(cmod_${pkg})

		set(pc_${pkg})
		if(PKG_CONFIG_PATH_LIST)
			find_file(pc_${pkg} ${pkg}.pc ${PKG_CONFIG_PATH_LIST})
		endif(PKG_CONFIG_PATH_LIST)

		if(pc_${pkg})

			# pkgconfig file found
			# ----------------------

			set(pkgconf_pkgs ${pkg})
			set(pkg_pc_str ${pkg}.pc)

			# select components as well
			if(${pkg}_COMPONENTS)
				get_filename_component(pc_${pkg}_path ${pc_${pkg}} PATH CACHE)
				foreach(comp ${${pkg}_COMPONENTS})
					find_file(pc_${pkg}_${comp} ${pkg}_${comp}.pc ${pc_${pkg}_path})
					if(pc_${pkg}_${comp})
						set(pkg_pc_str "${pkg_pc_str}, ${pkg}_${comp}.pc")
					else(pc_${pkg}_${comp})
						message(FATAL_ERROR "component ${comp} not found in package ${pkg}")
					endif(pc_${pkg}_${comp})
					list(APPEND pkgconf_pkgs ${pkg}_${comp})
				endforeach(comp ${${pkg}_COMPONENTS})
			endif(${pkg}_COMPONENTS)

			# run pkgconfig and gather flags
			pkg_check_modules(DFP_PKGCFG REQUIRED ${pkgconf_pkgs})

			if(${pkg}_STATIC)
				find_static_libs(DFP_PKGCFG_STATIC_LIBRARY_DIRS DFP_PKGCFG_STATIC_LIBRARIES DFP_PKGCFG_statlibs)

				set(DFP_PKGCFG_INCLUDE_DIRS 	${DFP_PKGCFG_STATIC_INCLUDE_DIRS})
				set(DFP_PKGCFG_LIBRARY_DIRS 	${DFP_PKGCFG_STATIC_LIBRARY_DIRS})
				set(DFP_PKGCFG_LIBRARIES 		${DFP_PKGCFG_statlibs})
				set(DFP_PKGCFG_CFLAGS_OTHER 	${DFP_PKGCFG_STATIC_CFLAGS_OTHER})
			endif(${pkg}_STATIC)

			message("rez_find_packages: found ${pkg_pc_str}")
			if(DFP_PKGCFG_INCLUDE_DIRS)
				message("    include dirs: ${DFP_PKGCFG_INCLUDE_DIRS}")
				list(APPEND ${DFP_PREFIX}_INCLUDE_DIRS 	${DFP_PKGCFG_INCLUDE_DIRS})
			endif(DFP_PKGCFG_INCLUDE_DIRS)
			if(DFP_PKGCFG_LIBRARY_DIRS)
				message("    library dirs: ${DFP_PKGCFG_LIBRARY_DIRS}")
				list(APPEND ${DFP_PREFIX}_LIBRARY_DIRS 	${DFP_PKGCFG_LIBRARY_DIRS})
			endif(DFP_PKGCFG_LIBRARY_DIRS)
			if(DFP_PKGCFG_LIBRARIES)
				message("    libraries:    ${DFP_PKGCFG_LIBRARIES}")
				list(APPEND ${DFP_PREFIX}_LIBRARIES 	${DFP_PKGCFG_LIBRARIES})
			endif(DFP_PKGCFG_LIBRARIES)
			if(DFP_PKGCFG_CFLAGS_OTHER)
				message("    definitions:  ${DFP_PKGCFG_CFLAGS_OTHER}")
				list(APPEND ${DFP_PREFIX}_DEFINITIONS 	${DFP_PKGCFG_CFLAGS_OTHER})
			endif(DFP_PKGCFG_CFLAGS_OTHER)

		else(pc_${pkg})
			if(DFP_REQUIRED)
				message(FATAL_ERROR "cmake module nor pkgconfig file could be found for package ${pkg}")
			endif(DFP_REQUIRED)
		endif(pc_${pkg})

	endif(cmod_${pkg})

	endforeach(pkg ${DFP_DEFAULT_ARGS})


	# remove duplicate flags
	#--------------------------------------------------------------------

	# remove duplicate cflags - don't do this for ldflags, there can be subtle cases wrt static linking
	# where duplicates are necessary.
	if(${DFP_PREFIX}_DEFINITIONS)
	#list(REMOVE_DUPLICATES ${DFP_PREFIX}_INCLUDE_DIRS)
	list(REMOVE_DUPLICATES ${DFP_PREFIX}_DEFINITIONS)
	endif(${DFP_PREFIX}_DEFINITIONS)


	# apply what we can
	#--------------------------------------------------------------------
	if(DFP_AUTO)

		include_directories(${${DFP_PREFIX}_INCLUDE_DIRS})
		include_directories(SYSTEM ${${DFP_PREFIX}_SYSTEM_INCLUDE_DIRS})
		link_directories(${${DFP_PREFIX}_LIBRARY_DIRS})

		# add cflags, escaping quotes along the way. add_definitions() will do this for you, however
		# non-define flags passed to add_definitions() are not picked up and passed to gcc by FindCUDA
		# macros. Similar problems may exist in other macros.

		list_to_string(cflags ${DFP_PREFIX}_DEFINITIONS)
		string(REPLACE "\"" "\\\"" cflags_ "${cflags}")
		set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${cflags_}")

	endif(DFP_AUTO)

endmacro (rez_find_packages)
