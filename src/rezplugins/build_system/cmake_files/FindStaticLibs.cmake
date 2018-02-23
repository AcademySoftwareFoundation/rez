#
# This is a utility function to get around problems when using pkg-config in combination with static
# library linking. Cmake has a 'pkg_check_modules' function, which runs pkgconfig and returns the
# results in a set of variables, one being <PREFIX>_LIBRARIES. However, if a library has both static
# and dynamic libs available, the libraries returned to cmake will be expanded by cmake into the
# dynamic libraries, not the static ones, even if pkgconfig has been invoked with its '--static'
# option. In truth pkgconfig shares some of the blame - the '--static' option just includes the libs
# in the 'Libs.private' section of the .pc file, and does nothing else.
#
# This macro takes a list of library search paths, and a list of libraries with no path or extension,
# and returns the same list of library names, but with a '.a' appended to those where a static
# version of the library was found in the library paths.
#
# We expect a list of library names (minus path or extension) because this is how cmake converts
# pkgconfig's '--libs' output into a list of libraries (basically - -lXXX strings with '-l' removed).
# And those libs that are static have '.a' appended, because on passing these to cmake's
# target_link_libraries() function, it knows they are static and creates the appropriate ldflags.
#
# Notes:
# Absolute path libs are left unchanged.
#
# Eg of usage:
#
# pkg_check_modules(pkgs REQUIRED foo)
# message(${pkgs_LIBRARIES})
# find_static_libs(pkgs_LIBRARY_DIRS pkgs_LIBRARIES outvar)
# message(${outvar})
#
# This might produce the messages:
#
# fooCore fooUtil
# fooCore.a fooUtil.a
#

macro (find_static_libs libdirsvar libsvar outvar)

	set(${outvar})

	foreach(lib ${${libsvar}})
		set(slib)	# stop find_file caching result
		find_file(slib lib${lib}.a ${${libdirsvar}})
		if(slib)
			list(APPEND ${outvar} ${lib}.a)
		else(slib)
			list(APPEND ${outvar} ${lib})
		endif(slib)
	endforeach(lib ${libs})

endmacro (find_static_libs libdirs libs outvar)
