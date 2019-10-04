#
# install_files_
# rez_install_files
#
# Macro for installing files. Unlike cmake's native 'install(FILES ...)' command,
# this macro preserves directory structure. Don't confuse with cmake's deprecated
# 'install_files' function. Files are installed as read-only.
#
# Usage: install_files_(
#	<files> [RELATIVE <rel_path>]
#	DESTINATION <rel_install_dir>
#	[EXECUTABLE]
#   [LOCAL_SYMLINK]
# )
#
# 'files' can be relative or absolute. Subdirectories are copied intact. RELATIVE lets
# you remove some of the file's relative path before it is installed. Note however that
# ALL files must be within the RELATIVE path, if RELATIVE is specified. If EXECUTABLE is
# present then the files will be installed with execute permissions. If LOCAL_SYMLINK
# is present it will create a symlink from the build package back to the source code
# for development/testing purposes. That way it is not necessary to do a rez-build every
# time the code changes.
#
# Example - take the files:
#
# - CMakeLists.txt
# - data/foo.a
# - data/detail/bah.a
#
# The command:
# install_files_(data/foo.a data/detail/bah.a DESTINATION mydata)
# will install files to:
# - <INSTALLDIR>/mydata/data/foo.a
# - <INSTALLDIR>/mydata/data/detail/bah.a
#
# install_files_(data/foo.a data/detail/bah.a DESTINATION .)
# will install files to:
# - <INSTALLDIR>/data/foo.a
# - <INSTALLDIR>/data/detail/bah.a
#
# install_files_(data/foo.a data/detail/bah.a RELATIVE data DESTINATION int)
# will install files to:
# - <INSTALLDIR>/int/foo.a
# - <INSTALLDIR>/int/detail/bah.a
#
# install_files_(data/foo.a data/detail/bah.a RELATIVE data DESTINATION .)
# will install files to:
# - <INSTALLDIR>/foo.a
# - <INSTALLDIR>/detail/bah.a
#
# install_files_(data/foo.a data/detail/bah.a RELATIVE data DESTINATION . LOCAL_SYMLINK )
# will create a symlink from:
# - <INSTALLDIR>/foo.a --> <SOURCEDIR>/foo.a
# - <INSTALLDIR>/detail/bah.a --><SOURCEDIR>/detail/bah.a

include(Utils)


# there isn't anything rez-specific here, but this matches name convention on other macros
macro (rez_install_files)
	install_files_(${ARGV})
endmacro (rez_install_files)


##########################################################################################
# get_target_filepath
##########################################################################################

# This is a helper macro which calculates the install location for the given file. 'filepath'
# is the file in question, relative to the current source directory. 'result' is set to the
# install location. This includes the filename, but not the absolute install directory.
macro (get_target_filepath filepath relative_arg destination_arg result)

	# cmake file(RELATIVE_PATH) is broken, only reason this is here
	set(rel_arg ${relative_arg})
	string(COMPARE EQUAL ${relative_arg} . is_dot)
	if(is_dot)
		set(rel_arg)
	endif(is_dot)
	string(COMPARE EQUAL "${relative_arg}" "./" is_dotslash)
	if(is_dotslash)
		set(rel_arg)
	endif(is_dotslash)

	set(fp ${filepath})
	if(NOT IS_ABSOLUTE ${filepath})
		set(fp ${CMAKE_CURRENT_SOURCE_DIR}/${filepath})
	endif(NOT IS_ABSOLUTE ${filepath})

	file(RELATIVE_PATH rel_f ${CMAKE_CURRENT_SOURCE_DIR}/${rel_arg} ${fp})
	set(${result} ${destination_arg}/${rel_f})

endmacro (get_target_filepath)


##########################################################################################
# install_files_
##########################################################################################

macro (install_files_)

	#
	# parse args
	#


	parse_arguments(INSTF "DESTINATION;RELATIVE" "EXECUTABLE;LOCAL_SYMLINK" ${ARGN})

	if(NOT INSTF_DEFAULT_ARGS)
		message(FATAL_ERROR "no files listed in call to install_files_")
	endif(NOT INSTF_DEFAULT_ARGS)

	list(GET INSTF_DESTINATION 0 dest_dir)
	if(NOT dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to install_files_")
	endif(NOT dest_dir)

	list(GET INSTF_RELATIVE 0 rel_dir)
	if(NOT rel_dir)
		set(rel_dir .)
	endif(NOT rel_dir)

	if(INSTF_EXECUTABLE)
		set(perms ${REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS})
	else(INSTF_EXECUTABLE)
		set(perms ${REZ_FILE_INSTALL_PERMISSIONS})
	endif(INSTF_EXECUTABLE)

	#
	# install files
	#
	foreach(f ${INSTF_DEFAULT_ARGS})
		get_target_filepath(${f} ${rel_dir} ${dest_dir} target_fpath)
		get_filename_component(target_path ${target_fpath} PATH)
        if(REZ_BUILD_TYPE STREQUAL "central" OR NOT INSTF_LOCAL_SYMLINK)
		    install(FILES ${f} DESTINATION ${target_path} PERMISSIONS ${perms})
        else()
            install( CODE "message (STATUS  \"Symlink : ${CMAKE_INSTALL_PREFIX}/${target_fpath} -> ${f}\" )" )
            install( CODE "execute_process(COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_INSTALL_PREFIX}/${target_path})" )
            install( CODE "execute_process(COMMAND ${CMAKE_COMMAND} -E create_symlink ${f} ${CMAKE_INSTALL_PREFIX}/${target_fpath})" )
        endif(REZ_BUILD_TYPE STREQUAL "central" OR NOT INSTF_LOCAL_SYMLINK)

	endforeach(f ${INSTF_DEFAULT_ARGS})

endmacro (install_files_)
