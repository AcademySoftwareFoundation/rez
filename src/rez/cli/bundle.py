'''
Bundle a context and its packages into a relocatable dir.
'''
from __future__ import print_function

import os
import os.path
import sys


def setup_parser(parser, completions=False):
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-s", "--skip-non-relocatable", action="store_true",
        help="leave non-relocatable packages non-bundled, rather than raise an error")
    group.add_argument(
        "-f", "--force", action="store_true",
        help="bundle package even if it isn't relocatable (use at your own risk)")
    group.add_argument(
        "-n", "--no-lib-patch", action="store_true",
        help="don't apply library patching within the bundle")
    parser.add_argument(
        "RXT",
        help="context to bundle")
    parser.add_argument(
        "DEST_DIR",
        help="directory to create bundle in; must not exist")


def command(opts, parser, extra_arg_groups=None):
    from rez.utils.logging_ import print_error
    from rez.bundle_context import bundle_context
    from rez.resolved_context import ResolvedContext

    rxt_filepath = os.path.abspath(os.path.expanduser(opts.RXT))
    dest_dir = os.path.abspath(os.path.expanduser(opts.DEST_DIR))

    # sanity checks
    if not os.path.exists(rxt_filepath):
        print_error("File does not exist: %s", rxt_filepath)
        sys.exit(1)

    context = ResolvedContext.load(rxt_filepath)

    bundle_context(
        context=context,
        dest_dir=dest_dir,
        force=opts.force,
        skip_non_relocatable=opts.skip_non_relocatable,
        verbose=opts.verbose,
        patch_libs=(not opts.no_lib_patch)
    )
