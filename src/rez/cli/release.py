'''
Build a package from source and deploy it.
'''
from __future__ import print_function
import os
import sys
from subprocess import call


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
    parser.add_argument(
        "--no-message", dest="no_message", action="store_true",
        help="do not prompt for release message.")
    setup_parser_common(parser)


def command(opts, parser, extra_arg_groups=None):
    from rez.build_process_ import create_build_process
    from rez.build_system import create_build_system
    from rez.release_vcs import create_release_vcs
    from rez.cli.build import get_build_args, get_current_developer_package
    from rez.config import config

    # load package
    working_dir = os.getcwd()
    package = get_current_developer_package()

    # create vcs
    vcs = create_release_vcs(working_dir, opts.vcs)

    # create build system
    build_args, child_build_args = get_build_args(opts, parser, extra_arg_groups)
    buildsys_type = opts.buildsys if ("buildsys" in opts) else None

    buildsys = create_build_system(working_dir,
                                   package=package,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   verbose=True,
                                   build_args=build_args,
                                   child_build_args=child_build_args)

    # create and execute release process
    builder = create_build_process(opts.process,
                                   working_dir,
                                   package=package,
                                   build_system=buildsys,
                                   vcs=vcs,
                                   ensure_latest=(not opts.no_latest),
                                   skip_repo_errors=opts.skip_repo_errors,
                                   ignore_existing_tag=opts.ignore_existing_tag,
                                   verbose=True)

    # get release message
    release_msg = opts.message
    filepath = None

    if config.prompt_release_message and not release_msg and not opts.no_message:
        from hashlib import sha1

        h = sha1(working_dir).hexdigest()
        filename = "rez-release-message-%s.txt" % h
        filepath = os.path.join(config.tmpdir, filename)

        header = "<Enter your release notes here>"
        changelog_token = "###<CHANGELOG>"

        if not os.path.exists(filepath):
            txt = header

            # get changelog and add to release notes file, for reference. They
            # get stripped out again before being added as package release notes.
            try:
                changelog = builder.get_changelog()
            except:
                pass

            if changelog:
                txt += ("\n\n%s This is for reference only - this line and all "
                        "following lines will be stripped from the release "
                        "notes.\n\n" % changelog_token)
                txt += changelog

            with open(filepath, 'w') as f:
                print(txt, file=f)

        call([config.editor, filepath])

        with open(filepath) as f:
            release_msg = f.read()

        # strip changelog out
        try:
            i = release_msg.index(changelog_token)
            release_msg = release_msg[:i]
        except ValueError:
            pass

        # strip header out
        release_msg = release_msg.replace(header, "")

        release_msg = release_msg.strip()

        if not release_msg:
            ch = None
            while ch not in ('A', 'a', 'C', 'c'):
                print("Empty release message. [A]bort or [C]ontinue release?")
                ch = raw_input()

            if ch in ('A', 'a'):
                print("Release aborted.")
                sys.exit(1)

    # perform the release
    builder.release(release_message=release_msg or None,
                    variants=opts.variants)

    # remove the release message file
    if filepath:
        try:
            os.remove(filepath)
        except:
            pass


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
