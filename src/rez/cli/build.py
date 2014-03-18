from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
import sys
import os



def command(opts, parser=None):
    working_dir = os.getcwd()

    def _args_err(args):
        parser.error("unrecognized arguments: %s" % ' '.join(str(x) for x in args))

    # parse buildsys and child buildsys args
    build_args = []
    child_build_args = []
    b_args = opts.BUILD_ARG
    if b_args:
        sep = "--"
        if sep in b_args:
            i = b_args.index(sep)
            if i:
                _args_err(b_args[:i])
            else:
                b_args = b_args[1:]
        else:
            _args_err(b_args)

        if sep in b_args:
            i = b_args.index(sep)
            build_args = b_args[:i]
            child_build_args = b_args[i+1:]
        else:
            build_args = b_args

    # create build system
    buildsys_type = opts.buildsys if ("buildsys" in opts) else None
    buildsys = create_build_system(working_dir,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   write_build_scripts=opts.scripts,
                                   install=opts.install,
                                   verbose=True,
                                   build_args=build_args,
                                   child_build_args=child_build_args)

    # create and execute build process
    builder = LocalSequentialBuildProcess(working_dir,
                                          buildsys,
                                          vcs=None)

    if not builder.build(install_path=opts.prefix,
                         clean=opts.clean):
        sys.exit(1)
