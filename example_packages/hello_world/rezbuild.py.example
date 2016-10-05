import os
import os.path
import shutil
import stat


def build(source_path, build_path, install_path, targets):

    def _build():
        # python source
        src_py = os.path.join(source_path, "python")
        dest_py = os.path.join(build_path, "python")

        if not os.path.exists(dest_py):
            shutil.copytree(src_py, dest_py)

        # binaries
        mode = (stat.S_IRUSR | stat.S_IRGRP |
                stat.S_IXUSR | stat.S_IXGRP)

        src_bin = os.path.join(source_path, "bin")
        dest_bin = os.path.join(build_path, "bin")

        if not os.path.exists(dest_bin):
            shutil.copytree(src_bin, dest_bin)

            for name in os.listdir(dest_bin):
                filepath = os.path.join(dest_bin, name)
                os.chmod(filepath, mode)

    def _install():
        for name in ("bin", "python"):
            src = os.path.join(build_path, name)
            dest = os.path.join(install_path, name)

            if os.path.exists(dest):
                shutil.rmtree(dest)

            print src
            print dest
            shutil.copytree(src, dest)

    _build()

    if "install" in (targets or []):
        _install()
