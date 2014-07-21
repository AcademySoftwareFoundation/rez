"""
Bake a launcher preset based on the resolution of a rez environment.
"""

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.resolver import RezService
from rez.contrib.animallogic.launcher.baker import Baker
from rez.config import config

def setup_parser(parser):

    parser.add_argument('--source', required=True, help='the preset/toolset to bake')
    parser.add_argument('--destination', required=True, help='the preset in which to store the result')
    parser.add_argument("--max-fails", type=int, default=-1, dest="max_fails",
                        metavar='N',
                        help="Abort if the number of failed configuration "
                        "attempts exceeds N")


def command(opts, parser):

    preset_proxy = client.HessianProxy(config.launcher_service_url + '/preset')
    toolset_proxy = client.HessianProxy(config.launcher_service_url + '/toolset')

    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)
    rez_service = RezService()

    baker = Baker(launcher_service, rez_service)
    baker.set_max_fails(opts.max_fails)
    baker.bake(opts.source, opts.destination)

