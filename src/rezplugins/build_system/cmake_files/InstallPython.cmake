#
# install_python
#
# Macro for building and installing python files.
#
# Usage:
# install_python(
#	<label>
#	FILES <py_files>
#	[RELATIVE <rel_path>]
#	[BIN <py_binary>]
#	DESTINATION <rel_install_dir>)
#
# 'label' is the cmake build target name for this set of python files.
#
# 'py_files' are the python scripts you wish to install.
#
# 'bin' is the python binary to use. If supplied, the python files are compiled (but not
# installed), to check for syntax errors.
#
# This macro behaves in the same way as rez_install_files with respect to the arguments RELATIVE and
# DESTINATION - please see InstallFiles.cmake documentation for further information.
#


include(Utils)
include(InstallFiles)


macro (install_python)

	#
	# parse args
	#

	parse_arguments(INSTPY "FILES;DESTINATION;RELATIVE;BIN" "" ${ARGN})

	list(GET INSTPY_DEFAULT_ARGS 0 label)
	if(NOT label)
		message(FATAL_ERROR "need to specify a label in call to install_python")
	endif(NOT label)

	list(GET INSTPY_DESTINATION 0 dest_dir)
	if(NOT dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to install_python")
	endif(NOT dest_dir)

	list(GET INSTPY_RELATIVE 0 rel_dir)
	if(NOT rel_dir)
		set(rel_dir .)
	endif(NOT rel_dir)

	if(NOT INSTPY_FILES)
		message(FATAL_ERROR "no files listed in call to install_python")
	endif(NOT INSTPY_FILES)

	list(GET INSTPY_BIN 0 py_bin)

	#
	# install .py's
	#
	if(py_bin)
		foreach(f ${INSTPY_FILES})

			set(fabs ${f})
			if(NOT IS_ABSOLUTE ${f})
				set(fabs ${CMAKE_CURRENT_SOURCE_DIR}/${f})
			endif(NOT IS_ABSOLUTE ${f})

			get_target_filepath(${fabs} ${rel_dir} ${dest_dir} target_fpath)
			set(local_f ${label}/${target_fpath})

			# can't work out how to implement a preinstall hook in cmake, so just copying
			# the py files as a custom install and doing the compile as part of that.
			get_filename_component(pycopy_path ${local_f} PATH)

			add_custom_command(
				OUTPUT ${local_f}
				COMMAND ${CMAKE_COMMAND} -E make_directory ${pycopy_path}
				COMMAND ${CMAKE_COMMAND} -E copy ${fabs} ${pycopy_path}
				COMMAND ${py_bin} -c 'import py_compile \; py_compile.compile(\"${local_f}\", None, None, True)'
			)

			get_filename_component(target_path ${target_fpath} PATH)
			install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${local_f} DESTINATION ${target_path})

			STRING(  REGEX REPLACE "[.]py" ".pyc" local_fc ${local_f} )
			install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${local_fc} DESTINATION ${target_path})

			list(APPEND pyfiles ${CMAKE_CURRENT_BINARY_DIR}/${local_f})
		endforeach(f ${INSTPY_FILES})

		add_custom_target ( ${label} ALL DEPENDS ${pyfiles} )

	else(py_bin)
		install_files_(${INSTPY_FILES} RELATIVE ${rel_dir} DESTINATION ${dest_dir})
	endif(py_bin)

endmacro (install_python)


















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
