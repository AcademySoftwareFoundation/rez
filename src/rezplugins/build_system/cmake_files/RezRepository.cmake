#
# macro:
# rez_set_archive
#
# usage:
# rez_set_archive(variable RELATIVE_PATH URL)
#
# This macro checks for the existence of a file at the given relative path, under
# the path specified by the environment variable $REZ_REPO_PAYLOAD_DIR. This
# file is typically a source archive, such as a .tgz.
#
# If the file doesn't exist, an error is raised. If it does, the path is written
# to 'variable'.
#
# This macro is used by many of the packages found in the 'repository' directory.
#

macro (rez_set_archive variable RELATIVE_PATH URL)

	if(NOT DEFINED ENV{REZ_REPO_PAYLOAD_DIR})
        message(FATAL_ERROR "REZ_REPO_PAYLOAD_DIR environment variable is not set")
    endif()

    set(archive $ENV{REZ_REPO_PAYLOAD_DIR}/${RELATIVE_PATH})

    if(EXISTS "${archive}")
    	set(${variable} ${archive})
    else()
    	message(FATAL_ERROR "Archive does not exist: ${archive}. Consider downloading it from ${URL}")
    endif()

endmacro (rez_set_archive)
