import sys
import shutil
import os
import os.path
from fnmatch import fnmatch


def copytree(src, dest):
    print("copying %s -> %s..." % (src, dest))
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


if __name__ == "__main__":
    src_path = sys.argv[1]
    install_path = sys.argv[2]

    # copy headers
    src_include_path = os.path.join(src_path, "include")
    dest_include_path = os.path.join(install_path, "include")
    copytree(src_include_path, dest_include_path)

    build_path = os.path.join(src_path, "build")

    # copy lib dirs
    for build in ("debug", "release"):
        patt = "*_%s" % build
        names = [x for x in os.listdir(build_path) if fnmatch(x, patt)]
        if names:
            path = os.path.join(build_path, names[0])
            dest_path = os.path.join(install_path, "lib", build)
            copytree(path, dest_path)
