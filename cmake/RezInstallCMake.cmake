#
# rez_install_cmake
#
# Macro for building and installing the cmake file for a project. The installed
# file will be called <unversioned_package_name>.cmake. This generated file will
# then be included by other projects using this one, via the 'rez_find_packages'
# macro. Note that, if using this macro, you should have a line in your package.yaml
# which includes the cmake file in CMAKE_MODULE_PATH, eg:
# - export CMAKE_MODULE_PATH=$CMAKE_MODULE_PATH:!ROOT!/cmake
#
# Arguments:
#
# DESTINATION: 	relative subdirectory to install the cmake file into.
#
# INCLUDE_DIRS: include directories. Any entries that are non-absolute paths are
# 				assumed to be a subdirectory of this package install.
#
# LIBRARY_DIRS: library directories. Any entries that are non-absolute paths are
# 				assumed to be a subdirectory of this package install.
#
# LIBRARIES: 	libraries to link against.
#
# DEFINITIONS: 	extra cflags.
#


if(NOT REZ_BUILD_ENV)
	message(FATAL_ERROR "Include RezBuild, not this cmake module directly.")
endif(NOT REZ_BUILD_ENV)

include(Utils)


macro(rez_install_cmake)

	#
	# parse args
	#

	parse_arguments(INSTCM
		"DESTINATION;INCLUDE_DIRS;LIBRARY_DIRS;LIBRARIES;DEFINITIONS"
		""
		${ARGN})

	list(GET INSTCM_DESTINATION 0 dest_dir)
	if(NOT dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to install_cmake")
	endif(NOT dest_dir)


	string(TOUPPER ${REZ_BUILD_PROJECT_NAME} UPNAME)
	set(_envtok "ENV{") # trick for escape shenannigans
	set(root_dir "$${_envtok}REZ_${UPNAME}_ROOT}")


	#
	# point non-absolute paths at the install dir for this package
	#

	foreach(inc_dir ${INSTCM_INCLUDE_DIRS})
		string(REGEX MATCH "^/" is_abs ${inc_dir})
		if(is_abs)
			list(APPEND inc_dirs ${inc_dir})
		else(is_abs)
			list(APPEND inc_dirs ${root_dir}/${inc_dir})
		endif(is_abs)
	endforeach(inc_dir ${INSTCM_INCLUDE_DIRS})

	foreach(lib_dir ${INSTCM_LIBRARY_DIRS})
		string(REGEX MATCH "^/" is_abs ${lib_dir})
		if(is_abs)
			list(APPEND lib_dirs ${lib_dir})
		else(is_abs)
			list(APPEND lib_dirs ${root_dir}/${lib_dir})
		endif(is_abs)
	endforeach(lib_dir ${INSTCM_LIBRARY_DIRS})


	#
	# generate the cmake file
	#

	set(projname $ENV{REZ_BUILD_PROJECT_NAME})
	set(cmake_file ${projname}.cmake)

	add_custom_command(
			OUTPUT ${dest_dir}/${cmake_file}
			COMMAND ${CMAKE_COMMAND} -E make_directory ${dest_dir}
			COMMAND echo set(${projname}_ROOT ${root_dir}) > ${dest_dir}/${cmake_file}
			COMMAND echo set(${projname}_INCLUDE_DIRS ${inc_dirs}) >> ${dest_dir}/${cmake_file}
			COMMAND echo set(${projname}_LIBRARY_DIRS ${lib_dirs}) >> ${dest_dir}/${cmake_file}
			COMMAND echo set(${projname}_LIBRARIES ${INSTCM_LIBRARIES}) >> ${dest_dir}/${cmake_file}
			COMMAND echo set(${projname}_DEFINITIONS ${INSTCM_DEFINITIONS}) >> ${dest_dir}/${cmake_file}
			COMMENT "Creating ${dest_dir}/${cmake_file}"
			VERBATIM
		)

	add_custom_target ( cmake ALL DEPENDS ${dest_dir}/${cmake_file} )

	install(
		FILES ${CMAKE_CURRENT_BINARY_DIR}/${dest_dir}/${cmake_file}
		DESTINATION ${dest_dir}
		PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS}
	)

endmacro(rez_install_cmake)






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
