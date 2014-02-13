"""
Tool for configuring and running cmake for the project in the current directory, and possibly make (or equivalent).

A 'package.yaml' file must exist in the current directory, and this drives the build. This utility is designed so
that it is possible to either automatically build an entire matrix for a given project, or to perform the build for
each variant manually. Note that in the following descriptions, 'make' is used to mean either make or equivalent.
The different usage scenarios are described below.

Usage case 1:

    rez-build [-v <variant_num>] [-m earliest|latest(default)] [-- cmake args]

This will use the package.yaml to spawn the correct shell for each variant, and create a 'build-env.sh' script (named
'build-env.0.sh,..., build-env.N.sh for each variant). Invoking one of these scripts will spawn an environment and
automatically run cmake with the supplied arguments - you can then execute make within this context, and this will
build the given variant. If zero or one variant exists, then 'build-env.sh' is generated.

Usage case 2:

    rez-build [[-v <variant_num>] [-n]] [-m earliest|latest(default)] -- [cmake args] -- [make args]

This will use the package.yaml to spawn the correct shell for each variant, invoke cmake, and then invoke make (or
equivalent). Use rez-build in this way to automatically build the whole build matrix. rez-build does a 'make clean'
before makeing by default, but the '-n' option suppresses this. Use -n in situations where you build a specific variant,
and then want to install that variant without rebuilding everything again. This option is only available when one
variant is being built, otherwise we run the risk of installing code that has been built for a different variant.

Examples of use:

Generate 'build-env.#.sh' files and invoke cmake for each variant, but do not invoke make:

    rez-build --

Builds all variants of the project, spawning the correct shell for each, and invoking make for each:

    rez-build -- --

Builds only the first variant of the project, spawning the correct shell, and invoking make:

    rez-build -v 0 -- --

Generate 'build-env.0.sh' and invoke cmake for the first (zeroeth) variant:

    rez-build -v 0 --

or:

    rez-build -v 0

Build the second variant only, and then install it, avoiding a rebuild:

    rez-build -v 1 -- --
    rez-build -v 1 -n -- -- install

"""

# FIXME: need to use raw help for text above

import sys
import os
import os.path
import argparse
from rez.cli import error, output
from rez.cmake import BUILD_SYSTEMS
from rez.settings import settings

#
#-#################################################################################################
# usage/parse args
#-#################################################################################################

# usage(){
#     /bin/cat $0 | grep '^##' | sed 's/^## //g' | sed 's/^##//g'
#     sys.exit(1)
# }
#
# [[ $# == 0 ]] && usage
# [[ "$1" == "-h" ]] && usage
#
#
# # gather rez-build args
# ARGS1=
#
#
# while [ $# -gt 0 ]; do
#     if [ "$1" == "--" ]:
#         shift
#         break
#     fi
#     ARGS1=$ARGS1" "$1
#     shift
# done
#
# if [ "$ARGS1" != "" ]:
#     while getopts iudgm:v:ns:c:t: OPT $ARGS1 ; do
#         case "$OPT" in
#             m)    opts.mode=$OPTARG
#                 ;;
#             v)    opts.variant_nums=$OPTARG
#                 ;;
#             n)    opts.no_clean=1
#                 ;;
#             s)    opts.vcs_metadata=$OPTARG
#                 ;;
#             c)  opts.changelog=$OPTARG
#                 ;;
#             t)    opts.time=$OPTARG
#                 ;;
#             i)    opts.print_install_path=1
#                 ;;
#             u)    opts.ignore_blacklist='--ignore-blacklist'
#                 ;;
#             g)    opts.no_archive='--ignore-archiving'
#                 ;;
#             d)    opts.no_assume_dt='--no-assume-dt'
#                 ;;
#             *)    sys.exit(1)
#                 ;;
#         esac
#     done
# fi


def setup_parser(parser):
    import rez.public_enums as enums
    parser.add_argument("-m", "--mode", dest="mode",
                        default=enums.RESOLVE_MODE_LATEST,
                        choices=[enums.RESOLVE_MODE_LATEST,
                                 enums.RESOLVE_MODE_EARLIEST,
                                 enums.RESOLVE_MODE_NONE],
                        help="set resolution mode")
    parser.add_argument("-v", "--variant", dest="variant_nums", type=int,
                        action='append',
                        help="individual variant to build")
    parser.add_argument("-t", "--time", dest="time", type=int,
                        default=0,
                        help="ignore packages newer than the given epoch time [default = current time]")
    # FIXME: --install-path is only used by rez-release. now that they are both python, we need to bring them closer together.
    parser.add_argument("-i", "--install-path", dest="print_install_path",
                        action="store_true", default=False,
                        help="print the path that the project would be installed to, and exit")
    parser.add_argument("-g", "--ignore-archiving", dest="ignore_archiving",
                        action="store_true", default=False,
                        help="silently ignore packages that have been archived")
    parser.add_argument("-u", "--ignore-blacklist", dest="ignore_blacklist",
                        action="store_true", default=False,
                        help="include packages that are blacklisted")
    parser.add_argument("-d", "--no-assume-dt", dest="no_assume_dt",
                        action="store_true", default=False,
                        help="do not assume dependency transitivity")
#     parser.add_argument("-c", "--changelog", dest="changelog",
#                         type=str,
#                         help="VCS changelog")
#     parser.add_argument("-r", "--release", dest="release_install",
#                         action="store_true", default=False,
#                         help="install packages to release directory")
    parser.add_argument("-s", "--build_mode-metadata", dest="vcs_metadata",
                        type=str,
                        help="VCS metadata")

    # cmake options
    parser.add_argument("--target", dest="build_target",
                        choices=['Debug', 'Release'],
                        default="Release",
                        help="build type")
    parser.add_argument("-b", "--build-system", dest="build_system",
                        choices=sorted(BUILD_SYSTEMS.keys()),
                        default=settings.build_system)
    parser.add_argument("--retain-cache", dest="retain_cmake_cache",
                        action="store_true", default=False,
                        help="retain cmake cache")

    # make options
    parser.add_argument("-n", "--no-clean", dest="no_clean",
                        action="store_true", default=False,
                        help="do not run clean prior to building")

    parser.add_argument('extra_args', nargs=argparse.REMAINDER,
                        help="remaining arguments are passed to make and cmake")

def command(opts):
    # separate out remaining args into cmake and make groups
    # e.g rez-build [args] -- [cmake args] -- [make args]
    if opts.extra_args:
        assert opts.extra_args[0] == '--'

    cmake_args = []
    make_args = []
    do_build = False
    if opts.extra_args:
        arg_list = cmake_args
        for arg in opts.extra_args[1:]:
            if arg == '--':
                # switch list
                arg_list = make_args
                do_build = True
                continue
            arg_list.append(arg)

    # -n option is disallowed if not building
    if not do_build and opts.no_clean:
        error("-n option is only supported when performing a build, eg 'rez-build -n -- --'")
        sys.exit(1)

    #-#################################################################################################
    # Extract info from package.yaml
    #-#################################################################################################

    if not os.path.isfile("package.yaml"):
        error("rez-build failed - no package.yaml in current directory.")
        sys.exit(1)

    #-#################################################################################################
    # Iterate over variants
    #-#################################################################################################

    import rez.release
    build_mode = rez.release.get_release_mode('.')
#     if build_mode.name == 'base':
#         # we only care about version control, so ignore the base release mode
#         build_mode = None
#
#     if build_mode and not opts.vcs_metadata:
#         url = build_mode.get_url()
#         opts.vcs_metadata = url if url else "(NONE)"

    build_mode.init(central_release=False)

    build_mode.build_time = opts.time

    build_mode.get_source()

    if not opts.variant_nums:
        opts.variant_nums = range(len(build_mode.variants))

    for varnum in opts.variant_nums:
        # set variant and create build directories
        build_mode._build_variant(varnum,
                                  build_system=opts.build_system,
                                  build_target=opts.build_target,
                                  mode=opts.mode,
                                  no_assume_dt=opts.no_assume_dt,
                                  do_build=do_build,
                                  additional_cmake_args=cmake_args,
                                  retain_cmake_cache=opts.retain_cmake_cache,
                                  make_args=make_args,
                                  make_clean=not opts.no_clean)


#    Copyright 2012 BlackGinger Pty Ltd (Cape Town, South Africa)
#
#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either metadata.version 3 of the License, or
#    (at your option) any later metadata.version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
