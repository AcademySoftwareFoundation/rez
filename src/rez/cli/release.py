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
        help="force the vcs system to use")
    parser.add_argument(
        "--no-latest", dest="no_latest", action="store_true",
        help="allows release of version earlier than the latest release.")
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
                                   verbose=True)

    builder.release(release_message=opts.message,
                    variants=opts.variants)
