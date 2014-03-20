from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
import sys
import os



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


def command(opts, parser=None):
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
