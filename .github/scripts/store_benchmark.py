from __future__ import print_function
import os
import os.path
import sys
import time

src_path = os.path.join(os.getcwd(), "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version  # noqa


if __name__ == "__main__":

    # create dated + versioned directory to store benchmark results
    destdir = time.strftime("%Y.%m.%d") + '-' + _rez_version
    destpath = os.path.join("metrics", "benchmarking", "artifacts", destdir)
    os.makedirs(destpath)

    # take the files that the artifact download created, and move them into
    # the version-specific directory
    artifact_files = [
        "resolves.json",
        "summary.json"
    ]

    for filename in artifact_files:
        os.rename(
            os.path.join("metrics", "benchmarking", filename),
            os.path.join(destpath, filename)
        )
