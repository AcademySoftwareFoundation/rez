"""
Bake a number launcher presets based on the resolution of a rez environment and
update a sync file with a superset of packages from all presets.  Another
process sync those packages to other sites (WAG or BB).
"""

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.resolver import RezService
from rez.contrib.animallogic.launcher.syncer import Syncer
from rez.config import config
import logging
import os.path


logger = logging.getLogger(__name__)


def setup_parser(parser):

    parser.add_argument("presets", type=str, nargs='+',
        help="the source presets/toolsets to bake.")
    parser.add_argument("--sync-file", type=str, metavar="FILE",
        help="update the given file with the list of packages.  If not provided"
        "the packages are printed to stdout.")
    parser.add_argument("--include-system-packages", default=False,
        action='store_true', help="automatically add system packages to the"
        "list to sync.")
    parser.add_argument("--include-rez-package", default=False,
        action='store_true', help="automatically add the rez package to the "
        "list to sync.")
    parser.add_argument("--detect-ext-links", default=False,
        action='store_true', help="detect if the package contains an 'ext'"
        "link include this.  Only 'ext' links pointing to a network location"
        "will be included")
    parser.add_argument("--relative-path", type=str,
        help="write package paths relative to this directory.")
    parser.add_argument("--max-fails", type=int, default=-1, dest="max_fails",
        metavar="N", help="abort the resolve if the number of failed "
            "configuration attempts exceeds N")


def command(opts, parser, extra_arg_groups=None):

    presets = opts.presets
    sync_file = opts.sync_file
    include_system_packages = opts.include_system_packages
    include_rez_package = opts.include_rez_package
    detect_ext_links = opts.detect_ext_links
    relative_path = opts.relative_path
    max_fails = opts.max_fails

    sync(presets, detect_ext_links=detect_ext_links, sync_file=sync_file,
         relative_path=relative_path, max_fails=max_fails,
         include_system_packages=include_system_packages,
         include_rez_package=include_rez_package)


def sync(presets, detect_ext_links=False, relative_path=None, max_fails=-1,
         include_system_packages=False, include_rez_package=False,
         sync_file=None):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    toolset_proxy = client.HessianProxy(config.launcher_service_url + "/toolset")

    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)
    rez_service = RezService()

    syncer = Syncer(launcher_service, rez_service, relative_path=relative_path)
    syncer.bake_presets(presets, max_fails=max_fails, detect_ext_links=detect_ext_links)

    if include_rez_package:
        syncer.add_rez_package_path()

    if include_system_packages:
        syncer.add_system_package_paths()

    sorted_paths_to_sync = syncer.get_sorted_paths_to_sync()

    if sync_file:
        syncer.log_paths_to_sync()

        logger.info("Writing to sync file %s." % sync_file)
        update_sync_file(sync_file, sorted_paths_to_sync)

    else:
        for path in sorted_paths_to_sync:
            print path


def update_sync_file(sync_file, paths_to_sync):

    HEAD_STRING = "# Start Rez Automated Package Sync List.\n"
    TAIL_STRING = "# End Rez Automated Package Sync List.\n"

    lines = [HEAD_STRING] + \
                map(lambda x: x + "\n", list(paths_to_sync)) + \
                [TAIL_STRING]

    if os.path.isfile(sync_file):
        update_existing_sync_file(sync_file, lines)

    else:
        write_sync_file(sync_file, lines)


def write_sync_file(sync_file, lines):

    with open(sync_file, "w") as fd:
        fd.writelines(lines)


def update_existing_sync_file(sync_file, new_lines):

    with open(sync_file, "r+") as fd:
        lines = fd.readlines()

        try:
            head_index = lines.index(new_lines[0])
            tail_index = lines.index(new_lines[-1]) + 1

            lines = lines[:head_index] + \
                            new_lines + \
                            lines[tail_index:]

        except ValueError:
            lines += ["\n"] + new_lines

        fd.seek(0)
        fd.writelines(lines)
