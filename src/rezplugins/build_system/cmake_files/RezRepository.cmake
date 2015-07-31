#
# macro:
# rez_set_archive
#
# ------------------------------
# Overview
# ------------------------------
#
# usage:
# rez_set_archive(variable RELATIVE_PATH)
#
# This macro checks for the existence of a file at the given relative path, under
# the path specified by the environment variable $REZ_REPO_PAYLOAD_DIR. This
# file is typically a source archive, such as a .tgz.
#
# If the file doesn't exist, an error is raised. If it does, the path is written
# to 'variable'.
#


macro (rez_set_archive)

    if(not ENV{REZ_REPO_PAYLOAD_DIR})
        message(FATAL_ERROR "REZ_REPO_PAYLOAD_DIR must be set")
    endif()

endmacro (rez_set_archive)
