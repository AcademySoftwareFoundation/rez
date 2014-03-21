from rez.build_process import LocalSequentialBuildProcess
from rez.cli.build import parse_build_args
from rez.build_system import create_build_system
from rez.release_vcs import create_release_vcs
import os
import sys



def command(opts, parser=None):
    working_dir = os.getcwd()
    build_args, child_build_args = parse_build_args(opts.BUILD_ARG, parser)

    # create vcs
    vcs = create_release_vcs(working_dir)

    # create build system
    buildsys_type = opts.buildsys if ("buildsys" in opts) else None
    buildsys = create_build_system(working_dir,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   verbose=True,
                                   build_args=build_args,
                                   child_build_args=child_build_args)

    # create and execute release process
    builder = LocalSequentialBuildProcess(working_dir,
                                          buildsys,
                                          vcs=vcs,
                                          release_message=opts.message)

    if not builder.release():
        sys.exit(1)
