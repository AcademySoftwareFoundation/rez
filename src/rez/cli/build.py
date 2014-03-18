from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
import os



def command(opts, parser=None):
    buildsys = None
    working_dir = os.getcwd()

    # todo
    build_child = True
    child_build_args = []
    build_args = []

    buildsys_type = opts.buildsys if ("buildsys" in opts) else None
    buildsys = create_build_system(working_dir,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   build_child=build_child,
                                   install=opts.install,
                                   verbose=True,
                                   child_build_args=child_build_args,
                                   *build_args)

    builder = LocalSequentialBuildProcess(working_dir,
                                          buildsys,
                                          vcs=None)

    builder.build(install_path=opts.prefix,
                  clean=opts.clean)
