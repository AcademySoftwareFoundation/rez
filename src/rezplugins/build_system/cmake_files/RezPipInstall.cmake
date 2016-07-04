#
# rez_pip_install
#
# Macro for installing python modules using pip.
#
# By default, the macro will install the package payload (.py, .pyc, .so etc
# files) into {root}/python, and any binaries into {root}/bin. You can provide
# PYTHONDIR and/or BINDIR to override this behavior.
#
# URL is the same url you would pass to pip - this can be an http url, or the
# filepath of a local archive (typically a tar.gz file).
#
# Pip args will be passed directly to pip when it runs the install. useful for verbosity
# or when defining custom include paths from other package in rez
#
# Usage:
# rez_pip_install(
#   <label>
#   URL <url>
#   [PYTHONDIR <pydir>]  # (default: 'python')
#   [BINDIR <bindir>]  # (default: 'bin')
#   [PIPARGS <pipargs>] # (default: '')
# )
#

if(NOT REZ_BUILD_ENV)
    message(FATAL_ERROR "RezPipInstall requires that RezBuild have been included beforehand.")
endif(NOT REZ_BUILD_ENV)

include(Utils)
include(ExternalProject)

macro (rez_pip_install)

    # --------------------------------------------------------------------------
    # parse args
    # --------------------------------------------------------------------------

    parse_arguments(PIPINST "URL;PYTHONDIR;BINDIR;PIPARGS" "" ${ARGN})

    list(GET PIPINST_DEFAULT_ARGS 0 label)
    if(NOT label)
        message(FATAL_ERROR "need to specify a label in call to rez_pip_install")
    endif(NOT label)

    list(GET PIPINST_URL 0 url)
    if(NOT url)
        message(FATAL_ERROR "need to specify URL in call to rez_pip_install")
    endif(NOT url)

    list(GET PIPINST_PYTHONDIR 0 pydir)
    if(NOT pydir)
        set(pydir "python")
    endif(NOT pydir)

    list(GET PIPINST_BINDIR 0 bindir)
    if(NOT bindir)
        set(bindir "bin")
    endif(NOT bindir)

    list(GET PIPINST_PIPARGS 0 pipargs)
    if(NOT pipargs)
        set(pipargs "bin")
    endif(NOT pipargs)

    # --------------------------------------------------------------------------
    # build/install
    #
    # Note: a 'build' is really just an install to a local staging directory.
    # --------------------------------------------------------------------------

    set(stagingpath "${CMAKE_BINARY_DIR}/staging")
    set(destpath "${stagingpath}/${pydir}")
    set(destbinpath "${stagingpath}/${bindir}")

    if(${REZ_BUILD_INSTALL})
        set(install_cmd ${CMAKE_COMMAND} -E copy_directory ${stagingpath} ${CMAKE_INSTALL_PREFIX} )
    else()
        set(install_cmd "")
    endif()

    # PIP on Windows doesn't like forward slashes for the --install-scripts argument
    file(TO_NATIVE_PATH ${destbinpath} destbinpath)

    ExternalProject_add(
        ${label}
        URL ${url}
        PREFIX ${label}
        UPDATE_COMMAND ""
        CONFIGURE_COMMAND ""
        INSTALL_COMMAND "${install_cmd}"
        BUILD_IN_SOURCE 1
        BUILD_COMMAND
            COMMAND ${CMAKE_COMMAND} -E make_directory ${destpath}
            COMMAND ${CMAKE_COMMAND} -E make_directory ${destbinpath}

            # Note the lack of double quotes where you would expect around --install-scripts=.
            # CMake escapes the quotes if I try; fortunately it works without.
            #
            COMMAND pip install --no-deps --target ${destpath} ${pipargs} --install-option=--install-scripts=${destbinpath} .
    )

endmacro (rez_pip_install)
