'''
Build a package from source.
'''
import sys
import os
import argparse

def parse_build_args(args, parser):
    def _args_err(args):
        parser.error("unrecognized arguments: %s" % ' '.join(str(x) for x in args))

    if args:
        sep = "--"
        if sep in args:
            i = args.index(sep)
            if i:
                _args_err(args[:i])
            else:
                args = args[1:]
        else:
            _args_err(args)

        if sep in args:
            i = args.index(sep)
            build_args = args[:i]
            child_build_args = args[i+1:]
            return (build_args, child_build_args)
        else:
            build_args = args
            return (build_args, [])
    else:
        return ([], [])

def add_build_system_args(parser):
    from rez.build_system import get_valid_build_systems
    clss = get_valid_build_systems(os.getcwd())

    if len(clss) == 1:
        cls = iter(clss).next()
        cls.bind_cli(parser)
    elif clss:
        types = [x.name() for x in clss]
        parser.add_argument("-b", "--build-system", dest="buildsys",
                            type=str, choices=types,
                            help="the build system to use.")

def add_extra_build_args(parser):
    parser.add_argument("BUILD_ARG", metavar="ARG", nargs=argparse.REMAINDER,
                        help="extra arguments to build system. To pass args to "
                        "a child build system also, list them after another "
                        "'--' arg.")

def setup_parser(parser):
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clear the current build before rebuilding.")
    parser.add_argument("-i", "--install", action="store_true",
                        help="install the build to the local packages path. "
                        "Use --prefix to choose a custom install path.")
    parser.add_argument("-p", "--prefix", type=str, metavar='PATH',
                        help="install to a custom path")
    parser.add_argument("-s", "--scripts", action="store_true",
                        help="create build scripts rather than performing the "
                        "full build. Running these scripts will place you into "
                        "a build environment, where you can invoke the build "
                        "system directly.")
    add_extra_build_args(parser)
    add_build_system_args(parser)

def command(opts, parser=None):
    from rez.build_process import LocalSequentialBuildProcess
    from rez.build_system import create_build_system
    working_dir = os.getcwd()
    build_args, child_build_args = parse_build_args(opts.BUILD_ARG, parser)

    # create build system
    buildsys_type = opts.buildsys if ("buildsys" in opts) else None
    buildsys = create_build_system(working_dir,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   write_build_scripts=opts.scripts,
                                   verbose=True,
                                   build_args=build_args,
                                   child_build_args=child_build_args)

    # create and execute build process
    builder = LocalSequentialBuildProcess(working_dir,
                                          buildsys,
                                          vcs=None)

    if not builder.build(install_path=opts.prefix,
                         clean=opts.clean,
                         install=opts.install):
        sys.exit(1)
