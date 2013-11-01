#
# This is a cmake file which defines a custom build macro. Some rez cmake code is used in
# this case (specifically, a utility macro for creating relative paths), but you don't have
# to have any rez cmake code in these cmake files, it can just be native cmake.
#
#
# Macro for converting text files to all uppercase.
# Usage:
# install_uppercase(
#	<label>
#	FILES <files>
#	[RELATIVE <rel_path>]
#	DESTINATION <rel_install_dir>)
#
# label: cmake built target name for this set of files.
#
# files: text files to convert to uppercase.
#
# RELATIVE and DESTINATION have the same meaning as in Rez's own InstallFiles rule, see
# there for more details.
#

include(Utils)
include(InstallFiles)


macro (install_uppercase)

	#
	# parse args
	#

	parse_arguments(TOUPPR "FILES;DESTINATION;RELATIVE" "" ${ARGN})

	list(GET TOUPPR_DEFAULT_ARGS 0 label)
	if(NOT label)
		message(FATAL_ERROR "need to specify a label in call to install_uppercase")
	endif(NOT label)

	list(GET TOUPPR_DESTINATION 0 dest_dir)
	if(NOT dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to install_uppercase")
	endif(NOT dest_dir)

	list(GET TOUPPR_RELATIVE 0 rel_dir)
	if(NOT rel_dir)
		set(rel_dir .)
	endif(NOT rel_dir)

	if(NOT TOUPPR_FILES)
		message(FATAL_ERROR "no files listed in call to install_uppercase")
	endif(NOT TOUPPR_FILES)


	#
	# build and install files
	#

	foreach(f ${TOUPPR_FILES})

		# have to deal with absolute and non-absolute paths because you might get either-or;
		# FILE(GLOB/GLOB_RECURSE) gives absolute, whereas a file list written by hand is
		# gonna be relative.
		set(fabs ${f})
		if(NOT IS_ABSOLUTE ${f})
			set(fabs ${CMAKE_CURRENT_SOURCE_DIR}/${f})
		endif(NOT IS_ABSOLUTE ${f})

		get_target_filepath(${fabs} ${rel_dir} ${dest_dir} target_fpath)
		set(local_f ${label}/${target_fpath})
		get_filename_component(fupper_path ${local_f} PATH)

		add_custom_command(
			OUTPUT ${local_f}
			COMMAND ${CMAKE_COMMAND} -E make_directory ${fupper_path}
			COMMAND ${CMAKE_COMMAND} -E copy ${fabs} ${fupper_path}
			# yes, escaping sed commands in cmake gets a bit nasty
			COMMAND gsed -i 's/\\\(.*\\\)/\\U\\1/' ${local_f}
			COMMENT "Making uppercase file ${CMAKE_CURRENT_BINARY_DIR}/${local_f}"
		)

		get_filename_component(target_path ${target_fpath} PATH)
		install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${local_f} DESTINATION ${target_path})

		list(APPEND ufiles ${CMAKE_CURRENT_BINARY_DIR}/${local_f})
	endforeach(f ${TOUPPR_FILES})

	add_custom_target ( ${label} ALL DEPENDS ${ufiles} )


endmacro (install_uppercase)










