"""
Create Eclipse project files (.project, .cproject, .pydevproject).
"""

from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
from rez.cli.build import setup_parser_common, get_build_args
from rez.contrib.animallogic.ide.eclipse import EclipseProjectBuilder
import os


def setup_parser(parser):

    parser.add_argument("--no-build", "-n", action="store_true")
    parser.add_argument("--build-project", action="store_true")
    parser.add_argument("--build-cproject", action="store_true")
    parser.add_argument("--build-cproject-settings", action="store_true")
    parser.add_argument("--build-pydevproject", action="store_true")

    setup_parser_common(parser)


def command(opts, parser, extra_arg_groups=None):

    working_dir = os.getcwd()

    if not opts.no_build:
        build_args, child_build_args = get_build_args(opts, parser, extra_arg_groups)
    
        buildsys_type = opts.buildsys if ("buildsys" in opts) else None
        buildsys = create_build_system(working_dir,
                                       buildsys_type=buildsys_type,
                                       opts=opts,
                                       write_build_scripts=True,
                                       verbose=True,
                                       build_args=build_args,
                                       child_build_args=child_build_args)
    
        builder = LocalSequentialBuildProcess(working_dir,
                                              buildsys,
                                              vcs=None)
    
        builder.build(clean=True, variants=opts.variants)

    files = ["build_project", "build_cproject", "build_cproject_settings", "build_pydevproject"]
    build_all = all([not getattr(opts, file_) for file_ in files])

    eclipse_project_builder = EclipseProjectBuilder(working_dir)

    if build_all:
        eclipse_project_builder.build_all()

    else:
        for file_ in files:
            if getattr(opts, file_):
                build_func = getattr(eclipse_project_builder, file_)
                build_func()

