from build_util import build_directory_recurse
import os.path


def build(context, source_path, build_path, install_path, targets):

    if "install" not in (targets or []):
        install_path = None

    build_directory_recurse(src_dir="nover",
                            dest_dir=os.path.join("python", "nover"),
                            source_path=source_path,
                            build_path=build_path,
                            install_path=install_path)
