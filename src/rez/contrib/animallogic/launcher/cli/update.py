"""
Updates a launcher preset.
"""
import sys

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.updater import Updater
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.config import config


def setup_parser(parser):

    parser.add_argument("--add-reference",  action='append',
        help="Add a new reference to the preset.")
    parser.add_argument("--remove-all-references", action='store_true', default=False,
        help="Remove all references from the target preset.")
    parser.add_argument("--description",
        help="A description for the preset change.")
    parser.add_argument('target', help='The target preset where the updates are going to be applied.')


def command(opts, parser, extra_arg_groups=None):

    reference_list = opts.add_reference
    remove_all_references = opts.remove_all_references
    description = opts.description
    target_preset = opts.target

    if not description:
        description = "Preset automatically updated by Rez. The command used was %s" % " ".join(sys.argv)

    update(target_preset, reference_list, description, remove_all_references)


def update(target, reference_list, description, remove_all_references, ):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    toolset_proxy = client.HessianProxy(config.launcher_service_url + "/toolset")
    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)

    replacer = Updater(launcher_service)

    replacer.update(target, reference_list, description, remove_all_references)

