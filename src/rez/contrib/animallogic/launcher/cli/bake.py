"""
Bake a launcher preset based on the resolution of a rez environment.
"""

from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.resolver import RezService
from rez.contrib.animallogic.launcher.baker import Baker
from rez.config import config
from hessian import client

def setup_parser(parser):

    parser.add_argument('--source', help='the preset to bake')
    parser.add_argument('--destination', help='the where to store the result')


def command(opts, parser):

    preset_proxy = client.HessianProxy(config.launcher_service_url + '/preset')
    toolset_proxy = client.HessianProxy(config.launcher_service_url + '/toolset')

    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)
    rez_service = RezService()

    baker = Baker(launcher_service, rez_service)
    baker.bake(opts.source, opts.destination)
