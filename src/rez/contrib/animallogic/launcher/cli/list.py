"""
List preset contents.  This command is analogous to the standard Linux 'ls'
command.
"""

from rez.config import config
from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service.hessian import LauncherHessianService
from rez.contrib.animallogic.launcher.model.preset import Preset
import datetime
import logging


logger = logging.getLogger(__name__)


def setup_parser(parser):

    parser.add_argument("preset", default="/Rez/applications",
                        help="The preset to list.")
    parser.add_argument("-l", "--long", default=False, action='store_true',
                        help="use a long listing format.")
    parser.add_argument("-R", "--recursive", default=False, action='store_true',
                        help="list submembers recursively.")
    parser.add_argument("-p", "--presets", default=False, action='store_true',
                        help="list presets only.")
    parser.add_argument("-f", "--format", default=None,
                        help="display the results using the provided format"
                        "string.  this option is ignored when used with"
                        "-l/--long.")


def command(opts, parser, extra_arg_groups=None):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    preset_path = opts.preset
    long_ = opts.long
    recursive = opts.recursive
    presets_only = opts.presets
    format_specification = opts.format
    date = datetime.datetime.now()

    if not format_specification:
        if long_:
            format_specification = config.launcher_long_list_format

        else:
            format_specification = config.launcher_list_format

    launcher_service = LauncherHessianService(preset_proxy, None)
    root = launcher_service.resolve_preset_path(preset_path, date)[-1]
    children = root.get_children(date, recursive=recursive)

    if presets_only:
        children = filter(lambda x: isinstance(x, Preset), children)

    if long_:
        parent_id = None
        for child in children:
            if (child.parent_id != parent_id or parent_id is None) and recursive:
                print ""
                print child.parent.get_path_relative_to_root(root)
                parent_id = child.parent_id
            print child.format(format_specification)

    else:
        if recursive:
            parent_id = None
            siblings = []
            for child in children:
                if (child.parent_id != parent_id or parent_id is None) and recursive:
                    print " ".join(child.format(format_specification) for child in siblings)

                    print ""
                    print child.parent.get_path_relative_to_root(root)
                    parent_id = child.parent_id
                    siblings = [child]

                else:
                    siblings.append(child)

        else:
            print " ".join(child.format(format_specification) for child in children)
