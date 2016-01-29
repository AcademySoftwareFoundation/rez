'''
Build a package from source and deploy it.
'''
import os
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
    from rez.cli.build import get_build_args
    from rez.config import config

    release_msg = opts.message
    filename = None

    if config.prompt_release_message and not release_msg and not opts.no_message:
        filename = os.path.join(config.tmpdir, "rez_release_message.tmp")

        with open(filename, "a+") as f:
            ed = config.editor
            call([ed, filename])

            read_data = f.read()
            if read_data:
                release_msg = read_data

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

    builder.release(release_message=release_msg,
                    variants=opts.variants)

    # remove the release message file
    if filename:
        os.remove(filename)
