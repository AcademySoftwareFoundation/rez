"""
Create Eclipse project files (.project, .cproject, .pydevproject).
"""

from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
from rez.cli.build import add_build_system_args
from rez.cli.build import add_extra_build_args
from rez.cli.build import parse_build_args
from rez.contrib.animallogic.ide.eclipse import EclipseProjectBuilder
import os
import sys


def setup_parser(parser):

    parser.add_argument("--variants", nargs='+', type=int,
                        help="select variants to build (zero-indexed).")

    add_build_system_args(parser)
    add_extra_build_args(parser)


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

    if not builder.build(clean=True, variants=opts.variants):
        sys.exit(1)
    
    eclipse_project_builder = EclipseProjectBuilder(working_dir)
    eclipse_project_builder.build_project()
    eclipse_project_builder.build_cproject()
    eclipse_project_builder.build_cproject_settings()
    eclipse_project_builder.build_pydevproject()

