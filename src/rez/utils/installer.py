from __future__ import print_function

import rez
from rez.package_maker import make_package
from rez.system import system
import os.path
import sys
import shutil


def install_as_rez_package(repo_path):
    """Install the current rez installation as a rez package.

    Note: This is very similar to 'rez-bind rez', however rez-bind is intended
    for deprecation. Rez itself is a special case.

    Args:
        repo_path (str): Repository to install the rez package into.
    """
    def commands():
        env.PYTHONPATH.append('{this.root}')  # noqa

    def make_root(variant, root):
        # copy source
        rez_path = rez.__path__[0]
        site_path = os.path.dirname(rez_path)
        rezplugins_path = os.path.join(site_path, "rezplugins")

        shutil.copytree(rez_path, os.path.join(root, "rez"))
        shutil.copytree(rezplugins_path, os.path.join(root, "rezplugins"))

    variant = system.variant
    variant.append("python-{0.major}.{0.minor}".format(sys.version_info))

    with make_package("rez", repo_path, make_root=make_root) as pkg:
        pkg.version = rez.__version__
        pkg.commands = commands
        pkg.variants = [variant]

    print('')
    print("Success! Rez was installed to %s/rez/%s" % (repo_path, rez.__version__))
