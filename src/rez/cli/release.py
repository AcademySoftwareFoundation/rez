'''
Build a package from source and deploy it.
'''
import os


def setup_parser(parser, completions=False):
    from rez.cli.build import setup_parser_common
    from rez.release_vcs import get_release_vcs_types
    vcs_types = get_release_vcs_types()
    parser.add_argument(
        "-m", "--message", type=str,
        help="release message")
    parser.add_argument(
        "--vcs", type=str, choices=vcs_types,
        help="force the vcs type to use")
    parser.add_argument(
        "--no-latest", dest="no_latest", action="store_true",
        help="allows release of version earlier than the latest release.")
    parser.add_argument(
        "--ignore-existing-tag", dest="ignore_existing_tag", action="store_true",
        help="perform the release even if the repository is already tagged at "
        "the current version. If the config setting plugins.release_vcs.check_tag "
        "is false, this option has no effect.")
    parser.add_argument(
        "--skip-repo-errors", dest="skip_repo_errors", action="store_true",
        help="release even if repository-related errors occur. DO NOT use this "
        "option unless you absolutely must release a package, despite there being "
        "a problem (such as inability to contact the repository server)")
    setup_parser_common(parser)


def command(opts, parser, extra_arg_groups=None):
    from rez.build_process_ import create_build_process
    from rez.build_system import create_build_system
    from rez.release_vcs import create_release_vcs
    from rez.cli.build import get_build_args

    working_dir = os.getcwd()

    # create vcs
    vcs = create_release_vcs(working_dir, opts.vcs)

    # create build system
    build_args, child_build_args = get_build_args(opts, parser, extra_arg_groups)
    buildsys_type = opts.buildsys if ("buildsys" in opts) else None
    buildsys = create_build_system(working_dir,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   verbose=True,
                                   build_args=build_args,
                                   child_build_args=child_build_args)

    # create and execute release process
    builder = create_build_process(opts.process,
                                   working_dir,
                                   build_system=buildsys,
                                   vcs=vcs,
                                   ensure_latest=(not opts.no_latest),
                                   skip_repo_errors=opts.skip_repo_errors,
                                   ignore_existing_tag=opts.ignore_existing_tag,
                                   verbose=True)

    builder.release(release_message=opts.message,
                    variants=opts.variants)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
