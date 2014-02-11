"""
Wrapper for cmake
"""
#!/bin/bash
# Dr. D Studios R&D
# Author : nicholas.yue@drdstudios.com
# and: allan.johns@drdstudios.com (added rez integration)
# Created : 25/March/2009
#
# Usage:
# rez-cmake [ rez-cmake args ] [ --- cmake args ]
#
# options:
#
# -t: set build type, one of: Debug, Release [default: Release]
#
# -o: turn on coverage profiling [default: off]
#
# -p: set build platform
#
# -c: install centrally [default: off]
#
# -i: set install directory - typically this is $HOME/packages
#
# -r: retain cmake cache [default: off]
#
# -d: set build directory
#
# -n: nop, ie do not run cmake. For debugging purposes only
#

import os
import subprocess
import argparse
import sys
from rez.cli import error, output
from rez.settings import settings

def setup_parser(parser):
    import rez.cmake
    parser.add_argument("-p", "--platform", dest="platform",
                        default="lin64",
                        help="build platform")
    parser.add_argument("-t", "--target", dest="build_target",
                        choices=['Debug', 'Release'],
                        default="Release",
                        help="build type")
    parser.add_argument("-b", "--build-system", dest="build_system",
                        choices=sorted(rez.cmake.BUILD_SYSTEMS.keys()),
                        default=settings.build_system)
    parser.add_argument("-i", "--install-directory", dest="install_dir",
                        default=os.environ['REZ_LOCAL_PACKAGES_PATH'],
                        help="install directory. [default = $REZ_LOCAL_PACKAGES_PATH (%(default)s)]")
    parser.add_argument("-d", "--build-directory", dest="build_directory",
                        default='.',
                        help="build directory.")
    parser.add_argument("-r", "--retain-cache", dest="retain_cache",
                        action="store_true", default=False,
                        help="retain cmake cache")
    parser.add_argument("-o", "--coverage", dest="coverage",
                        action="store_true", default=False,
                        help="turn on coverage profiling")
    parser.add_argument("-c", "--central-install", dest="central_install",
                        action="store_true", default=False,
                        help="install packages centrally")
    parser.add_argument("-n", "--nop", dest="nop",
                        action="store_true", default=False,
                        help="do not run cmake")
    parser.add_argument('extra_args', nargs=argparse.REMAINDER,
                        help="remaining arguments are passed to make and cmake")

def command(opts):
    import rez.cmake
    import platform

    if opts.nop:
        sys.exit(0)

    if opts.central_install:
        if os.environ.get('REZ_IN_REZ_RELEASE') != "1":
            result = raw_input("You are attempting to install centrally outside of rez-release: do you really want to do this (y/n)? ")
            if result != "y":
                sys.exit(1)

    # Do we delete the cache
    if not opts.retain_cache:
        rez.cmake.remove_cache()

    cmake_arguments = rez.cmake.get_cmake_args(opts.build_system, 
                                               opts.build_target, 
                                               release_install=opts.central_install, 
                                               coverage=opts.coverage)

    extra_cmake_arguments = [x for x in opts.extra_args if x != '---']

    # Add pass-through cmake arguments
    cmake_arguments.extend(extra_cmake_arguments)

    # Append build directory [must be last append before command generation]
    cmake_arguments.append(opts.build_directory)

    print "rez-cmake: calling cmake with the following arguments: %s" % ' '.join(cmake_arguments)

    exitcode = subprocess.call(['cmake'] + cmake_arguments)
    sys.exit(exitcode)



#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
