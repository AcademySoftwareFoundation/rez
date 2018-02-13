#
# install_dirs_
# rez_install_dirs
#
# Macro for installing directories. Very similar to cmake's native install(DIRECTORY), but
# is more convenient to use. Files are installed as read-only. svn files (any file within
# a .svn dir) are excluded. If this macro does not provide enough fine-grain control for
# your needs, then you should use cmake's install(DIRECTORY) macro instead (and you should
# use the values REZ_FILE_INSTALL_PERMISSIONS and REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS
# to specify the permissions you want).If LOCAL_SYMLINK is preset it would create a symlink
# from the build package back to the source code for development/testing purposes. That way
# a rez-build is not needed every time that the code changes.
#
# Usage: install_dirs_(
#	<directories>
#	DESTINATION <rel_install_dir>
#	[EXECUTABLE]
#	[LOCAL_SYMLINKS]
# )
#

include(Utils)


# there isn't anything rez-specific here, but this matches name convention on other macros
macro (rez_install_dirs)
	install_dirs_(${ARGV})
endmacro (rez_install_dirs)


macro (install_dirs_)

	#
	# parse args
	#

	parse_arguments(INSTD "DESTINATION" "EXECUTABLE;LOCAL_SYMLINK" ${ARGN})

	if(NOT INSTD_DEFAULT_ARGS)
		message(FATAL_ERROR "no directories listed in call to install_dirs_")
	endif(NOT INSTD_DEFAULT_ARGS)

	list(GET INSTD_DESTINATION 0 dest_dir)
	if(NOT dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to install_dirs_")
	endif(NOT dest_dir)

	if(INSTD_EXECUTABLE)
		set(perms ${REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS})
	else(INSTD_EXECUTABLE)
		set(perms ${REZ_FILE_INSTALL_PERMISSIONS})
	endif(INSTD_EXECUTABLE)

    if(REZ_BUILD_TYPE STREQUAL "central" OR NOT INSTD_LOCAL_SYMLINK)
        install(DIRECTORY
            ${INSTD_DEFAULT_ARGS}
            DESTINATION ${dest_dir}
            FILE_PERMISSIONS ${perms}
            PATTERN .svn EXCLUDE
            )
    else()
        install(CODE "execute_process(COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_INSTALL_PREFIX}/${dest_dir})" )
        foreach(directory ${INSTD_DEFAULT_ARGS})
            get_filename_component(DIR_NAME ${directory} NAME)
            install(CODE "message (STATUS  \"Symlink : ${CMAKE_CURRENT_SOURCE_DIR}/${directory} -> ${CMAKE_INSTALL_PREFIX}/${dest_dir}/${DIR_NAME}\" )" )
            install(CODE "execute_process(COMMAND ${CMAKE_COMMAND} -E create_symlink ${CMAKE_CURRENT_SOURCE_DIR}/${directory} ${CMAKE_INSTALL_PREFIX}/${dest_dir}/${DIR_NAME})" )
        endforeach(directory ${INSTD_DEFAULT_ARGS})
    endif(REZ_BUILD_TYPE STREQUAL "central" OR NOT INSTD_LOCAL_SYMLINK)


endmacro (install_dirs_)
