#
# macro:
# rez_project
#
# Use this macro in lieu of cmake's native 'project' macro, when writing projects
# that use rez-build. The project name is not an argument to the macro - it is
# read from the package.py instead.


macro (rez_project)

    # As a Windows compiler and build environment isn't correctly setup (yet),
    # stop CMake performing automatic compiler discovery (and failing).
    if (CMAKE_SYSTEM_NAME STREQUAL "Windows")
        project(${REZ_BUILD_PROJECT_NAME} NONE)
    elseif()
        project(${REZ_BUILD_PROJECT_NAME})
    endif()

endmacro (rez_project)
