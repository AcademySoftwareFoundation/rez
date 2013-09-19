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
import stat
import os.path
import shutil
import subprocess
import argparse
import textwrap
from rez.cli import error, output

BUILD_SYSTEMS = {'eclipse' : "Eclipse CDT4 - Unix Makefiles",
                 'codeblocks' : "CodeBlocks - Unix Makefiles",
                 'make' : "Unix Makefiles",
                 'xcode' : "Xcode"}

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

def unversioned(pkgname):
    return pkgname.split('-')[0]

def _get_package_metadata(filepath, quiet=False, no_catch=False):
    from rez.rez_metafile import ConfigMetadata
    # load yaml
    if no_catch:
        metadata = ConfigMetadata(filepath)
    else:
        try:
            metadata = ConfigMetadata(filepath)
        except Exception as e:
            if not quiet:
                error("Malformed package.yaml: '" + filepath + "'." + str(e))
            sys.exit(1)

    if not metadata.version:
        if not quiet:
            error("No 'metadata.version' in " + filepath + ".\n")
        sys.exit(1)

    if metadata.name:
        # FIXME: this should be handled by ConfigMetadata class
        bad_chars = [ '-', '.' ]
        for ch in bad_chars:
            if (metadata.name.find(ch) != -1):
                error("Package name '" + metadata.name + "' contains illegal character '" + ch + "'.")
                sys.exit(1)
    else:
        if not quiet:
            error("No 'name' in " + filepath + ".")
        sys.exit(1)
    return metadata

def _get_variants(metadata, variant_nums):
    all_variants = metadata.get_variants()
    if all_variants:
        if variant_nums:
            variants = []
            for variant_num in variant_nums:
                try:
                    variants.append((variant_num, all_variants[variant_num]))
                except IndexError:
                    error("Variant #" + str(variant_num) + " does not exist in package.")
            return variants
        else:
            # get all variants
            return [(i, var) for i, var in enumerate(all_variants)]
    else:
        return [(-1, None)]

def _format_bash_command(args):
    def quote(arg):
        if ' ' in arg:
            return "'%s'" % arg
        return arg
    cmd = ' '.join([quote(arg) for arg in args ])
    return textwrap.dedent("""
        echo
        echo rez-build: calling \\'%(cmd)s\\'
        %(cmd)s
        if [ $? -ne 0 ]; then
            exit 1 ;
        fi
        """ % {'cmd' : cmd})

def get_cmake_args(build_system, build_target):
    cmake_arguments = ["-DCMAKE_SKIP_RPATH=1"]

    # Rez custom module location
    cmake_arguments.append("-DCMAKE_MODULE_PATH=$CMAKE_MODULE_PATH")

    # Fetch the initial cache if it's defined
    if 'CMAKE_INITIAL_CACHE' in os.environ:
        cmake_arguments.extend(["-C", "$CMAKE_INITIAL_CACHE"])

    cmake_arguments.extend(["-G", build_system])

    cmake_arguments.append("-DCMAKE_BUILD_TYPE=%s" % build_target)
    return cmake_arguments

def _chmod(path, mode):
    if stat.S_IMODE(os.stat(path).st_mode) != mode:
        os.chmod(path, mode)

# def foo():
#     if print_build_requires:
#         build_requires = metadata.get_build_requires()
#         if build_requires:
#             strs = str(' ').join(build_requires)
#             print strs
#     
#     if print_requires:
#         requires = metadata.get_requires()
#         if requires:
#             strs = str(' ').join(requires)
#             print strs
#     
#     if print_help:
#         if metadata.help:
#             print str(metadata.help)
#         else:
#             if not quiet:
#                 error("No 'help' entry specified in " + filepath + ".")
#             sys.exit(1)
#     
#     if print_tools:
#         tools = metadata.metadict.get("tools")
#         if tools:
#             print str(' ').join(tools)
#     
#     if (variant_num != None):
#         variants = metadata.get_variants()
#         if variants:
#             if (variant_num >= len(variants)):
#                 if not quiet:
#                     error("Variant #" + str(variant_num) + " does not exist in package.")
#                 sys.exit(1)
#             else:
#                 strs = str(' ').join(variants[variant_num])
#                 print strs
#         else:
#             if not quiet:
#                 error("Variant #" + str(variant_num) + " does not exist in package.")
#             sys.exit(1)

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
    parser.add_argument("-c", "--changelog", dest="changelog",
                        type=str,
                        help="VCS changelog")
    parser.add_argument("-s", "--vcs-metadata", dest="vcs_metadata",
                        type=str,
                        help="VCS metadata")

    # cmake options
    parser.add_argument("--target", dest="build_target",
                        choices=['Debug', 'Release'],
                        default="Release",
                        help="build type")
    parser.add_argument("-b", "--build-system", dest="build_system",
                        choices=sorted(BUILD_SYSTEMS.keys()),
                        type=lambda x: BUILD_SYSTEMS[x],
                        default='eclipse')
    parser.add_argument("-r", "--retain-cache", dest="retain_cache",
                        action="store_true", default=False,
                        help="retain cmake cache")

    # make options
    parser.add_argument("-n", "--no-clean", dest="no_clean",
                        action="store_true", default=False,
                        help="do not run clean prior to building")

    parser.add_argument('extra_args', nargs=argparse.REMAINDER,
                        help="remaining arguments are passed to make and cmake")

def command(opts):
    import rez.rez_filesys
    from rez.rez_util import get_epoch_time
    from . import config as rez_cli_config

    now_epoch = get_epoch_time()
    cmake_args = get_cmake_args(opts.build_system, opts.build_target)

    # separate out remaining args into cmake and make groups
    # e.g rez-build [args] -- [cmake args] -- [make args]
    if opts.extra_args:
        assert opts.extra_args[0] == '--'

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

    # any packages newer than this time will be ignored. This serves two purposes:
    # 1) It stops inconsistent builds due to new packages getting released during a build;
    # 2) It gives us the ability to reproduce a build that happened in the past, ie we can make
    # it resolve the way that it did, rather than the way it might today
    if not opts.time:
        opts.time = now_epoch

    #-#################################################################################################
    # Extract info from package.yaml
    #-#################################################################################################

    if not os.path.isfile("package.yaml"):
        error("rez-build failed - no package.yaml in current directory.")
        sys.exit(1)

    metadata = _get_package_metadata(os.path.abspath("package.yaml"))
    reqs = metadata.get_requires(include_build_reqs=True) or []

    variants = _get_variants(metadata, opts.variant_nums)

    #-#################################################################################################
    # Iterate over variants
    #-#################################################################################################
    
    # FIXME: use rez.rez_release for this once rez-*-print-url and rez-*-changelog are converted to python
    if os.path.isdir('.git'):
        VCS='git'
    elif os.path.isdir('.svn'):
        VCS='svn'
    elif os.path.isdir('.hg'):
        VCS='hg'
    else:
        VCS = None

    if VCS and not opts.vcs_metadata:
        pass
        # TODO:
        #opts.vcs_metadata=`rez-$VCS-print-url`

    build_dir_base = os.path.abspath("build")
    build_dir_id = os.path.join(build_dir_base, ".rez-build")

    for variant_num, variant in variants:
        # set variant and create build directories
        variant_str = ' '.join(variant)
        if variant_num == -1:
            build_dir = build_dir_base
            cmake_dir_arg = "../"

            if opts.print_install_path:
                output(os.path.join(os.environ['REZ_RELEASE_PACKAGES_PATH'],
                                    metadata.name, metadata.version))
                continue
        else:
            build_dir = os.path.join(build_dir_base, str(variant_num))
            cmake_dir_arg = "../../"

            build_dir_symlink = os.path.join(build_dir_base, '_'.join(variant))
            variant_subdir = os.path.join(*variant)

            if opts.print_install_path:
                output(os.path.join(os.environ['REZ_RELEASE_PACKAGES_PATH'],
                                    metadata.name, metadata.version, variant_subdir))
                continue

            print
            print "---------------------------------------------------------"
            print "rez-build: building for variant '%s'" % variant_str
            print "---------------------------------------------------------"

        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        if variant and not os.path.islink(build_dir_symlink):
            os.symlink(os.path.basename(build_dir), build_dir_symlink)

        src_file = os.path.join(build_dir, 'build-env.sh')
        env_bake_file = os.path.join(build_dir, 'build-env.context')
        actual_bake = os.path.join(build_dir, 'build-env.actual')
        dot_file = os.path.join(build_dir, 'build-env.context.dot')
        changelog_file = os.path.join(build_dir, 'changelog.txt')

        # allow the svn pre-commit hook to identify the build directory as such
        with open(build_dir_id, 'w') as f:
            f.write('')

        meta_file = os.path.join(build_dir, 'info.txt')
        # store build metadata
        with open(meta_file, 'w') as f:
            import getpass
            f.write("ACTUAL_BUILD_TIME: %d"  % now_epoch)
            f.write("BUILD_TIME: %d" % opts.time)
            f.write("USER: %s" % getpass.getuser())
            f.write("SVN: %s" % opts.vcs_metadata)

        # store the changelog into a metafile (rez-release will specify one
        # via the -c flag)
        if not opts.changelog:
            if not VCS:
                with open(changelog_file, 'w') as f:
                    f.write('not under version control')
            else:
                pass
                # TODO:
                #rez-$VCS-changelog > $changelog_file
        else:
            shutil.copy(opts.changelog, changelog_file)

        # attempt to resolve env for this variant
        print
        print "rez-build: invoking rez-config with args:"
        #print "$opts.no_archive $opts.ignore_blacklist $opts.no_assume_dt --time=$opts.time"
        print "requested packages: %s" % (', '.join(reqs + variant))
        print "package search paths: %s" % (os.environ['REZ_PACKAGES_PATH'])

#         # Note: we pull latest version of cmake into the env
#         rez-config
#             $opts.no_archive
#             $opts.ignore_blacklist
#             --print-env
#             --time=$opts.time
#             $opts.no_assume_dt
#             --dot-file=$dot_file
#             $reqs $variant cmake=l > $env_bake_file
# 
#         if [ $? != 0 ]:
#             rm -f $env_bake_file
#             print "rez-build failed - an environment failed to resolve." >&2
#             sys.exit(1)

        # setup args for rez-config
        # TODO: provide a util which reads defaults for the cli function
        kwargs = dict(pkg=(reqs + variant + ['cmake=l']),
                      verbosity=0,
                      version=False,
                      print_env=False,
                      print_dot=False,
                      meta_info='tools',
                      meta_info_shallow='tools',
                      env_file=env_bake_file,
                      dot_file=dot_file,
                      max_fails=-1,
                      wrapper=False,
                      no_catch=False,
                      no_path_append=False,
                      print_pkgs=False,
                      quiet=False,
                      no_local=False,
                      buildreqs=False,
                      no_cache=False,
                      no_os=False)
        # copy settings that are the same between rez-build and rez-config
        kwargs.update(vars(opts))
    
        config_opts = argparse.Namespace(**kwargs)

        try:
            rez_cli_config.command(config_opts)
        except Exception, err:
            error("rez-build failed - an environment failed to resolve.\n" + str(err))
            if os.path.exists(dot_file):
                os.remove(dot_file)
            if os.path.exists(env_bake_file):
                os.remove(env_bake_file)
            sys.exit(1)

        # TODO: this shouldn't be a separate step
        # create dot-file
        # rez-config --print-dot --time=$opts.time $reqs $variant > $dot_file

        text = textwrap.dedent("""\
            #!/bin/bash

            # because of how cmake works, you must cd into same dir as script to run it
            if [ "./build-env.sh" != "$0" ] ; then
                echo "you must cd into the same directory as this script to use it." >&2
                exit 1
            fi

            source %(env_bake_file)s
            export REZ_CONTEXT_FILE=%(env_bake_file)s
            env > %(actual_bake)s

            # need to expose rez-config's cmake modules in build env
            [[ CMAKE_MODULE_PATH ]] && export CMAKE_MODULE_PATH=%(rez_path)s/cmake';'$CMAKE_MODULE_PATH || export CMAKE_MODULE_PATH=%(rez_path)s/cmake

            # make sure we can still use rez-config in the build env!
            export PATH=$PATH:%(rez_path)s/bin

            echo
            echo rez-build: in new env:
            rez-context-info

            # set env-vars that CMakeLists.txt files can reference, in this way
            # we can drive the build from the package.yaml file
            export REZ_BUILD_ENV=1
            export REZ_BUILD_PROJECT_VERSION=%(version)s
            export REZ_BUILD_PROJECT_NAME=%(name)s
            """ % dict(env_bake_file=env_bake_file,
                       actual_bake=actual_bake,
                       rez_path=rez.rez_filesys._g_rez_path,
                       version=metadata.version,
                       name=metadata.name))

        if reqs:
            text += "export REZ_BUILD_REQUIRES_UNVERSIONED='%s'\n" % (' '.join([unversioned(x) for x in reqs]))

        if variant_num != -1:
            text += "export REZ_BUILD_VARIANT='%s'\n" % variant_str
            text += "export REZ_BUILD_VARIANT_UNVERSIONED='%s'\n" % (' '.join([unversioned(x) for x in variant]))
            text += "export REZ_BUILD_VARIANT_SUBDIR=/%s/\n" % variant_subdir

        if not opts.retain_cache:
            text += _format_bash_command(["rm", "-f", "CMakeCache.txt"])

        # cmake invocation
        text += _format_bash_command(["cmake", "-d", cmake_dir_arg] + cmake_args)

        if do_build:
            # TODO: determine build tool from --build-system? For now just assume make

            if not opts.no_clean:
                text += _format_bash_command(["make", "clean"])

            text += _format_bash_command(["make"] + make_args)

            with open(src_file, 'w') as f:
                f.write(text + '\n')
            _chmod(src_file, 0777)

            # run the build
            # TODO: add the 'cd' into the script itself
            p = subprocess.Popen([os.path.join('.', os.path.basename(src_file))],
                                 cwd=os.path.dirname(src_file))
            p.communicate()
            if p.returncode != 0 :
                error("rez-build failed - there was a problem building. returned code %s" % (p.returncode,))
                sys.exit(1)

        else:
            text += 'export REZ_ENV_PROMPT=">$REZ_ENV_PROMPT"\n'
            text += "export REZ_ENV_PROMPT='BUILD>'\n"
            text += "/bin/bash --rcfile %s/bin/rez-env-bashrc\n" % rez.rez_filesys._g_rez_path

            with open(src_file, 'w') as f:
                f.write(text + '\n')
            _chmod(src_file, 0777)

            if variant_num == -1:
                print "Generated %s, invoke to run cmake for this project." % src_file
            else:
                print "Generated %s, invoke to run cmake for this project's variant:(%s)" % (src_file, variant_str)


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
