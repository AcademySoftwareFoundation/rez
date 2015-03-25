#
# rez_install_doxygen
#
# Macro for building and installing doxygen files for rez projects. Take special note of the
# DOXYPY option if you want to build docs for python source.
#
# Usage:
# rez_install_doxygen(
#	<label>
#	FILES <files>
#	DESTINATION <rel_install_dir>
#	[DOXYFILE <doxyfile>]
#	[DOXYDIR <dir>]
#	[IMAGEPATH <dir>]
#   [FORCE]
#	[DOXYPY]
# )
#
# <label>: This becomes the name of this cmake target. Eg 'doc'.
# DESTINATION: Relative path to install resulting docs to. Typically Doxygen will create a 
# directory (often 'html'), which is installed into <install_path>/<rel_install_dir>/html.
#
# DOXYFILE: The doxygen config file to use. If unspecified, Rez will use its own default config.
#
# DOXYDIR: The directory the docs will be generated in, defaults to 'html'. You only need to set
# this if you're generating non-html output (for eg, by setting GENERATE_HTML=NO in a custom Doxyfile).
#
# IMAGEPATH: The directory that images are found in.
#
# FORCE: Normally docs are not installed unless a central installation is taking place - set this
# arg to force doc building and installation always.
#
# DOXYPY: At the time of writing, Doxygen does not have good python support. A separate, GPL project
# called 'doxypy' (http://code.foosel.org/doxypy) can be used to fix this - it lets you write 
# doxygen-style comments in python docstrings, and extracts them correctly. Doxypy cannot be shipped
# with Rez since its license is incompatible - in order to use it, Rez expects you to install it 
# yourself, and then make it available by binding it to Rez (as you would any 3rd party software) 
# as a package called 'doxypy', with the doxypy.py file in the package root. Once you've done this,
# and you specify the DOXYPY option, you get complete python Doxygen support (don't forget to include
# the doxypy package as a build_requires). You can then comment your python code in doxygen style, 
# like so:
#
# def myFunc(foo):
#   """
#   @param foo The foo.
#   @return Something foo-like.
#   """
#
# Note: Consider adding a rez-help entry to your package.yaml like so:
# help: firefox file://!ROOT!/<DESTINATION>/<DOXYDIR>/index.html
# Then, users can just go "rez-help <pkg>", and the doxygen help will appear.
#

if(NOT REZ_BUILD_ENV)
	message(FATAL_ERROR "RezInstallDoxygen requires that RezBuild have been included beforehand.")
endif(NOT REZ_BUILD_ENV)

INCLUDE(Utils)

FIND_PACKAGE(Doxygen)


macro (rez_install_doxygen)

	if(DOXYGEN_EXECUTABLE)
		parse_arguments(INSTDOX "FILES;DESTINATION;DOXYFILE;DOXYDIR;IMAGEPATH" "FORCE;DOXYPY;USE_TAGFILES;GENERATE_TAGFILE" ${ARGN})

		list(GET INSTDOX_DEFAULT_ARGS 0 label)
		if(NOT label)
			message(FATAL_ERROR "need to specify a label in call to rez_install_doxygen")
		endif(NOT label)

		list(GET INSTDOX_DESTINATION 0 dest_dir)
		if(NOT dest_dir)
			message(FATAL_ERROR "need to specify DESTINATION in call to rez_install_doxygen")
		endif(NOT dest_dir)

		if(NOT INSTDOX_FILES)
			message(FATAL_ERROR "no files listed in call to rez_install_doxygen")
		endif(NOT INSTDOX_FILES)

		list(GET INSTDOX_DOXYFILE 0 doxyfile)
		if(NOT doxyfile)
			set(doxyfile $ENV{REZ_BUILD_DOXYFILE})
		endif(NOT doxyfile)

		list(GET INSTDOX_DOXYDIR 0 doxydir)
		if(NOT doxydir)
			set(doxydir html)
		endif(NOT doxydir)

		set(_filter_source_files "")
		set(_input_filter "")
		set(_opt_output_java "")
		set(_extract_all "")
		if(INSTDOX_DOXYPY)
			find_file(DOXYPY_SRC doxypy.py $ENV{REZ_DOXYPY_ROOT})
			if(DOXYPY_SRC)
				set(_filter_source_files "FILTER_SOURCE_FILES = YES")
				set(_input_filter "INPUT_FILTER = \"python ${DOXYPY_SRC}\"")
				set(_opt_output_java "OPTIMIZE_OUTPUT_JAVA = YES")
				set(_extract_all "EXTRACT_ALL = YES")
			else(DOXYPY_SRC)
				message(FATAL_ERROR "Cannot locate doxypy.py - you probably need to supply doxypy as a Rez package, see the documentation in <rez_install>/cmake/RezInstallDoxygen.cmake for more info.")
			endif(DOXYPY_SRC)
		endif(INSTDOX_DOXYPY)

        set(_proj_name $ENV{REZ_BUILD_PROJECT_NAME})
        set(_proj_ver $ENV{REZ_BUILD_PROJECT_VERSION})
        set(_proj_desc $ENV{REZ_BUILD_PROJECT_DESCRIPTION})
		string(REPLACE "\n" " " _proj_desc2 ${_proj_desc})

		set(_tagfile "")
		set(_tagfiles "")

		if (INSTDOX_GENERATE_TAGFILE)
		    set(_tagfile ${_proj_name}.tag)
			set(_generate_tagfile "GENERATE_TAGFILE = ${_tagfile}")
		endif ()

		if (INSTDOX_USE_TAGFILES)
			set(_tagfiles "TAGFILES += $(DOXYGEN_TAGFILES)")
		endif ()

		add_custom_command(
			OUTPUT ${dest_dir}/Doxyfile
			DEPENDS ${doxyfile}
			COMMAND ${CMAKE_COMMAND} -E make_directory ${dest_dir}
			COMMAND ${CMAKE_COMMAND} -E copy ${doxyfile} ${dest_dir}/Doxyfile
			COMMAND chmod +w ${dest_dir}/Doxyfile
			COMMAND echo PROJECT_NAME = \"${_proj_name}\" >> ${dest_dir}/Doxyfile
			COMMAND echo PROJECT_NUMBER = \"${_proj_ver}\" >> ${dest_dir}/Doxyfile
			COMMAND echo PROJECT_BRIEF = \"${_proj_desc2}\" >> ${dest_dir}/Doxyfile
			COMMAND echo ${_filter_source_files} >> ${dest_dir}/Doxyfile
			COMMAND echo ${_input_filter} >> ${dest_dir}/Doxyfile
			COMMAND echo ${_opt_output_java} >> ${dest_dir}/Doxyfile
			COMMAND echo ${_extract_all} >> ${dest_dir}/Doxyfile
			COMMAND echo ${_tagfiles} >> ${dest_dir}/Doxyfile
			COMMAND echo ${_generate_tagfile} >> ${dest_dir}/Doxyfile
			COMMAND echo INPUT = ${INSTDOX_FILES} >> ${dest_dir}/Doxyfile
			COMMAND echo IMAGE_PATH = ${CMAKE_SOURCE_DIR}/${INSTDOX_IMAGEPATH} >> ${dest_dir}/Doxyfile
			COMMAND echo STRIP_FROM_PATH = ${CMAKE_SOURCE_DIR} >> ${dest_dir}/Doxyfile
			COMMENT "Generating Doxyfile ${dest_dir}/Doxyfile..."
			VERBATIM
		)

		add_custom_target(${label}
			DEPENDS ${dest_dir}/Doxyfile
			#COMMAND ${DOXYGEN_EXECUTABLE}
			COMMAND doxygen
			WORKING_DIRECTORY ${dest_dir}
			COMMENT "Generating doxygen content in ${dest_dir}/${doxydir}..."
		)

		if(REZ_BUILD_TYPE STREQUAL "central" OR INSTDOX_FORCE)
			# only install docs when installing centrally
			add_custom_target(_install_${label} ALL DEPENDS ${label})
			install(DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/${dest_dir}/${doxydir} DESTINATION ${dest_dir})

			if (INSTDOX_GENERATE_TAGFILE)
				install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${dest_dir}/${_tagfile} DESTINATION ${dest_dir})
			endif ()

		endif(CENTRAL OR INSTDOX_FORCE)
	else(DOXYGEN_EXECUTABLE)
		message(WARNING "RezInstallDoxygen cannot find Doxygen - documentation was not built.")
	endif(DOXYGEN_EXECUTABLE)
endmacro (rez_install_doxygen)
