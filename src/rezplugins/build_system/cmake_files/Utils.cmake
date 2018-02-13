
# This utility macro converts a list into a space-separated string.
# Really this should be native to cmake
macro(list_to_string outvar listvar)
	set(${outvar})
	foreach(str ${${listvar}})
		set(${outvar} "${${outvar}} ${str}")
	endforeach(str ${${listvar}})
endmacro(list_to_string outvar listvar)



# This utility macro determines whether a particular string value
# occurs within a list of strings:
#
#  list_contains(result string_to_find arg1 arg2 arg3 ... argn)
#
# This macro sets the variable named by var equal to TRUE if
# string_to_find is found anywhere in the following arguments.
macro(list_contains var value)
   set(${var})
   foreach (value2 ${ARGN})
     if (${value} STREQUAL ${value2})
       set(${var} TRUE)
     endif (${value} STREQUAL ${value2})
   endforeach (value2)
endmacro(list_contains)



# This utility macro strips out items of the list that match
# the given regular expression
#
#  list_remove_regex(listvar regex)
#
macro(list_remove_regex listvar regex)
    set(temp)
    set(match ${regex})
    foreach(str ${${listvar}})
        if (NOT ${str} MATCHES ${match})
            list(APPEND temp ${str})
        endif (NOT ${str} MATCHES ${match})
    endforeach(str ${${listvar}})
    set(${listvar} "${temp}")
endmacro(list_remove_regex listvar regex)



# This utility macro extracts the first argument from the list of
# arguments given, and places it into the variable named var.
#
#   car(var arg1 arg2 ...)
macro(car var)
   set(${var} ${ARGV1})
endmacro(car)



# This utility macro extracts all of the arguments given except the
# first, and places them into the variable named var.
#
#   car(var arg1 arg2 ...)
macro(cdr var junk)
   set(${var} ${ARGN})
endmacro(cdr)



# The PARSE_ARGUMENTS macro will take the arguments of another macro and
# define several variables. The first argument to PARSE_ARGUMENTS is a
# prefix to put on all variables it creates. The second argument is a
# list of names, and the third argument is a list of options. Both of
# these lists should be quoted. The rest of PARSE_ARGUMENTS are
# arguments from another macro to be parsed.
#
#     PARSE_ARGUMENTS(prefix arg_names options arg1 arg2...)
#
# For each item in options, PARSE_ARGUMENTS will create a variable with
# that name, prefixed with prefix_. So, for example, if prefix is
# MY_MACRO and options is OPTION1;OPTION2, then PARSE_ARGUMENTS will
# create the variables MY_MACRO_OPTION1 and MY_MACRO_OPTION2. These
# variables will be set to true if the option exists in the command line
# or false otherwise.
#
# For each item in arg_names, PARSE_ARGUMENTS will create a variable
# with that name, prefixed with prefix_. Each variable will be filled
# with the arguments that occur after the given arg_name is encountered
# up to the next arg_name or the end of the arguments. All options are
# removed from these lists. PARSE_ARGUMENTS also creates a
# prefix_DEFAULT_ARGS variable containing the list of all arguments up
# to the first arg_name encountered.
#
# Usage examples:
# ExampleMacro( myLibary SRCDIRS mysrcs TESTDIRS myTests MODULARIZED)
# ExampleMacro( anotherLib )
# ExampleMacro( thirdLib TESTDIRS myTests)
#
MACRO(PARSE_ARGUMENTS prefix arg_names option_names)
   SET(DEFAULT_ARGS)
   FOREACH(arg_name ${arg_names})
     SET(${prefix}_${arg_name})
   ENDFOREACH(arg_name)
   FOREACH(option ${option_names})
     SET(${prefix}_${option} FALSE)
   ENDFOREACH(option)

   SET(current_arg_name DEFAULT_ARGS)
   SET(current_arg_list)
   FOREACH(arg ${ARGN})
     LIST_CONTAINS(is_arg_name ${arg} ${arg_names})
     IF (is_arg_name)
       SET(${prefix}_${current_arg_name} ${current_arg_list})
       SET(current_arg_name ${arg})
       SET(current_arg_list)
     ELSE (is_arg_name)
       LIST_CONTAINS(is_option ${arg} ${option_names})
       IF (is_option)
       SET(${prefix}_${arg} TRUE)
       ELSE (is_option)
       SET(current_arg_list ${current_arg_list} ${arg})
       ENDIF (is_option)
     ENDIF (is_arg_name)
   ENDFOREACH(arg)
   SET(${prefix}_${current_arg_name} ${current_arg_list})
ENDMACRO(PARSE_ARGUMENTS)


# this utility macro sets the given C++ linker flags globally,
# ie all targets will inherit them automatically
MACRO(SET_GLOBAL_LINKER_CXX_FLAGS)
	set(ldflags_ ${ARGN})
	list_to_string(ldflags ldflags_)
	SET(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${ldflags}")
	SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${ldflags}")
	SET(CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS} ${ldflags}")
ENDMACRO(SET_GLOBAL_LINKER_CXX_FLAGS)



##########################################################################
# Boost Utilities                                                        #
##########################################################################
# Copyright (C) 2007 Douglas Gregor <doug.gregor@gmail.com>              #
# Copyright (C) 2007 Troy Straszheim                                     #
#                                                                        #
# Distributed under the Boost Software License, Version 1.0.             #
# See accompanying file LICENSE_1_0.txt or copy at                       #
#   http://www.boost.org/LICENSE_1_0.txt                                 #
##########################################################################
# Macros in this module:                                                 #
#                                                                        #
#   list_contains: Determine whether a string value is in a list.        #
#                                                                        #
#   car: Return the first element in a list                              #
#                                                                        #
#   cdr: Return all but the first element in a list                      #
#                                                                        #
#   parse_arguments: Parse keyword arguments for use in other macros.    #
##########################################################################
