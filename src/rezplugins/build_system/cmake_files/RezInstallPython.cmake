#
# rez_install_python
#
# Macro for building and installing python files for rez projects. This is the same as install_python,
# except that it ensures that a python package is being used, and uses the appropriate python binary.
#
# Usage:
# rez_install_python(<label>
#                    FILES <py_files>
#                    [RELATIVE <rel_path>]
#                    [LOCAL_SYMLINK]
#                    DESTINATION <rel_install_dir>)
#


if(NOT REZ_BUILD_ENV)
	message(FATAL_ERROR "RezInstallPython requires that RezBuild have been included beforehand.")
endif(NOT REZ_BUILD_ENV)


include(Utils)
include(InstallPython)


macro (rez_install_python)

	#
	# check that 'python' is in the environment. All 'python' packages should expose a 'rez-python'
	# binary (whether that be symlink/wrapper script etc), the following build command relies
	# on this, so that the correct version of the python interpreter is used to compile.
	#

	list_contains(pyfound python ${REZ_BUILD_ALL_PKGS})
	if(NOT pyfound)
		message(FATAL_ERROR "a version of python must be listed as a requirement when using the 'rez_install_python' macro. Packages for this build are: ${REZ_BUILD_ALL_PKGS}")
	endif(NOT pyfound)

	install_python(${ARGV} BIN python)

endmacro (rez_install_python)
