from __future__ import print_function

import shutil
import os.path
import os
import sys


def build(source_path, build_path, install_path, targets):

    def _copy(src, dest):
        print("copying %s to %s..." % (src, dest))
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    # build
    src = os.path.join(source_path, "data")
    dest = os.path.join(build_path, "data")
    _copy(src, dest)

    if "install" not in (targets or []):
        return

    # install
    src = os.path.join(build_path, "data")
    dest = os.path.join(install_path, "data")
    _copy(src, dest)


if __name__ == '__main__':
    build(
        source_path=os.environ['REZ_BUILD_SOURCE_PATH'],
        build_path=os.environ['REZ_BUILD_PATH'],
        install_path=os.environ['REZ_BUILD_INSTALL_PATH'],
        targets=sys.argv[1:]
    )
