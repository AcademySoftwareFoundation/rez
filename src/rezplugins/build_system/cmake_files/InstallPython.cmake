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
#   [LOCAL_SYMLINK]
#	DESTINATION <rel_install_dir>)
#
# 'label' is the cmake build target name for this set of python files.
#
# 'py_files' are the python scripts you wish to install.
#
# 'bin' is the python binary to use. If supplied, the python files are compiled (but not
# installed), to check for syntax errors.
#
# This macro behaves in the same way as rez_install_files with respect to the arguments
# RELATIVE, DESTINATION and LOCAL_SYMLINK - please see InstallFiles.cmake documentation
# for further information.
#
# A note on the use of LOCAL_SYMLINK: If set, pyc files are not generated.
#


include(Utils)
include(InstallFiles)


macro (install_python)

	# --------------------------------------------------------------------------
	# parse args
	# --------------------------------------------------------------------------

	parse_arguments(INSTPY "FILES;DESTINATION;RELATIVE;BIN" "LOCAL_SYMLINK" ${ARGN})

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

	if($ENV{REZ_BUILD_INSTALL_PYC})
		set(install_pyc 1)
	endif($ENV{REZ_BUILD_INSTALL_PYC})

	list(GET INSTPY_BIN 0 py_bin)

	# cancel compiling if local symlinking enabled
	if(INSTPY_LOCAL_SYMLINK)
	    unset(py_bin)
	    set(LOCAL_SYMLINK_ARG "LOCAL_SYMLINK")
	endif(INSTPY_LOCAL_SYMLINK)


	# --------------------------------------------------------------------------
	# install .py's and .pyc's
	# --------------------------------------------------------------------------

	if(py_bin)
		foreach(f ${INSTPY_FILES})
			set(fabs ${f})
			if(NOT IS_ABSOLUTE ${f})
				set(fabs ${CMAKE_CURRENT_SOURCE_DIR}/${f})
			endif(NOT IS_ABSOLUTE ${f})

			get_target_filepath(${fabs} ${rel_dir} ${dest_dir} target_fpath)
			get_filename_component(target_path ${target_fpath} PATH)
			set(local_f ${label}/${target_fpath})
			set(local_fc "${local_f}c")
			get_filename_component(pycopy_path ${local_f} PATH)


			# ------------------------------------------------------------------
			# py file
			# ------------------------------------------------------------------

			install(FILES ${fabs} DESTINATION ${target_path})


			# ------------------------------------------------------------------
			# pyc file
			# ------------------------------------------------------------------

			add_custom_command(
				OUTPUT ${local_fc}
				COMMAND ${CMAKE_COMMAND} -E make_directory ${pycopy_path}
				COMMAND ${py_bin} -c 'import py_compile \; py_compile.compile(\"${fabs}\", \"${local_fc}\", None, True)'
				DEPENDS ${fabs}
			)

			if(install_pyc)
				install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${local_fc} DESTINATION ${target_path})
				list(APPEND pycfiles ${CMAKE_CURRENT_BINARY_DIR}/${local_fc})
			endif(install_pyc)


		endforeach(f ${INSTPY_FILES})

		add_custom_target ( ${label} ALL DEPENDS ${pyfiles} ${pycfiles} )

	else(py_bin)
		install_files_(
			${INSTPY_FILES}
			RELATIVE ${rel_dir}
			${LOCAL_SYMLINK_ARG}
			DESTINATION ${dest_dir})
	endif(py_bin)

endmacro (install_python)
