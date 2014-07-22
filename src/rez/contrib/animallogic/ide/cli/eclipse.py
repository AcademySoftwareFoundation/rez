"""
Create Eclipse project files (.project, .cproject, .pydevproject).
"""

from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
from rez.cli.build import setup_parser_common
from rez.cli.build import add_extra_build_args, add_build_system_args, parse_build_args
from rez.contrib.animallogic.ide.eclipse import EclipseProjectBuilder
import os
import sys


def setup_parser(parser):

    parser.add_argument("--build-project", action="store_true")
    parser.add_argument("--build-cproject", action="store_true")
    parser.add_argument("--build-cproject-settings", action="store_true")
    parser.add_argument("--build-pydevproject", action="store_true")

    add_extra_build_args(parser)
    add_build_system_args(parser)
#    setup_parser_common(parser)


def command(opts, parser):

    working_dir = os.getcwd()

    build_args, child_build_args = parse_build_args(opts.BUILD_ARG, parser)

    buildsys_type = opts.buildsys if ("buildsys" in opts) else None
    buildsys = create_build_system(working_dir,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   write_build_scripts=False,
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

