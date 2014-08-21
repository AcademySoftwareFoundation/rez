import shutil
import os.path


def build(source_path, build_path, install_path, targets):

    def _copy(src, dest):
        print "copying %s to %s..." % (src, dest)
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
