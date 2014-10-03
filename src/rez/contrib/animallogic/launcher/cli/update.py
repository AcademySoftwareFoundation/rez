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
                           help="the reference launcher path to replace in the destination preset.")
    parser.add_argument("--remove-all-references", action='store_true', default=False,
                         help="Remove all references to preset from the target preset")
    parser.add_argument("--description",
                        help="a description for the reference change.")
    parser.add_argument('target', help='the target preset where the updates are going to be applied ')


def command(opts, parser, extra_arg_groups=None):

    reference_list = opts.add_reference
    remove_all_references = opts.remove_all_references
    description = opts.description
    target_preset = opts.target

    if not description:
        description = "Preset automatically updated by Rez. The command used was %s" % " ".join(sys.argv)
    print target_preset
    print reference_list
    print description
    print remove_all_references

    update(target_preset, reference_list, description,remove_all_references)


def update(target, reference_list, description, remove_all_references, ):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    toolset_proxy = client.HessianProxy(config.launcher_service_url + "/toolset")
    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)

    replacer = Updater(launcher_service)

    replacer.update(target, reference_list, description, remove_all_references)

