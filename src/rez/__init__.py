import os.path

__version__ = "2.0.ALPHA.52"
__author__ = "Allan Johns"
__license__ = "LGPL"

module_root_path = __path__[0]

install_package_base = module_root_path
for i in range(6):
    install_package_base = os.path.dirname(install_package_base)
