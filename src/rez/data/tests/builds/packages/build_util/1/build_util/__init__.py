from __future__ import print_function

import shutil
import os.path



def build_directory_recurse(src_dir, dest_dir, source_path, build_path,
                            install_path=None):

    def _copy(src, dest):
        print("copying %s to %s..." % (src, dest))
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    # build
    src = os.path.join(source_path, src_dir)
    dest = os.path.join(build_path, dest_dir)
    _copy(src, dest)

    if not install_path:
        return

    # install
    src = os.path.join(build_path, dest_dir)
    dest = os.path.join(install_path, dest_dir)
    _copy(src, dest)


def check_visible(module, try_module):
    try:
        __import__(try_module, {})
    except ImportError as e:
        raise Exception(("%s's rezbuild.py should have been able to access "
                        "%s! Error: %s") % (module, try_module, str(e)))
