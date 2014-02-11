"""
rez cmake

Some useful functions for interacting with cmake.
"""

import os
import platform
from rez.exceptions import RezError
from rez.settings import settings

BUILD_SYSTEMS = {'eclipse': "Eclipse CDT4 - Unix Makefiles",
                 'codeblocks': "CodeBlocks - Unix Makefiles",
                 'make': "Unix Makefiles",
                 'xcode': "Xcode"}

class RezCMakeError(RezError):
    """
    rez cmake error
    """

def remove_cache():
    if os.path.exists("CMakeCache.txt"):
        os.remove("CMakeCache.txt")

def validate_build_system(build_system):
    if build_system == 'xcode' and platform.system() != 'Darwin':
        raise RezCMakeError("Generation of Xcode project only available on the OSX platform")

def get_cmake_args(build_system, build_target, release_install=False, coverage=False):

    validate_build_system(build_system)
    
    cmake_arguments = settings.cmake_args if settings.cmake_args else []
    cmake_arguments.extend(["-DCMAKE_MODULE_PATH=$CMAKE_MODULE_PATH"])

    if 'CMAKE_INITIAL_CACHE' in os.environ:
        cmake_arguments.extend(["-C", "$CMAKE_INITIAL_CACHE"])

    cmake_arguments.extend(["-G", BUILD_SYSTEMS[build_system]])
    cmake_arguments.append("-DCMAKE_BUILD_TYPE=%s" % build_target)

    if release_install:
        cmake_arguments.append("-DCENTRAL=1")

    if coverage:
        cmake_arguments.append("-DCOVERAGE=1")

    return cmake_arguments

