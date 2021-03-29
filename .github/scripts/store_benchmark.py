from __future__ import print_function
import os
import os.path
import json
import sys
import shutil
import time

src_path = os.path.join(os.getcwd(), "src", "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version  # noqa


# max number of result artifacts to store
MAX_ARTIFACTS = 50

benchmarking_dir = os.path.join("src", "metrics", "benchmarking")


def store_result():
    # create dated + versioned directory to store benchmark results
    # Dir in the form:
    #
    #     YYYY.MM.DD-PYMAJOR.PYMINOR-REZVER
    #
    destdir = '-'.join((
        time.strftime("%Y.%m.%d"),
        "%d.%d" % sys.version_info[:2],
        _rez_version
    ))

    destpath = os.path.join(benchmarking_dir, "artifacts", destdir)
    if os.path.exists(destpath):
        return

    os.makedirs(destpath)

    # take the files that the artifact download created, and move them into
    # the versioned directory
    artifact_files = [
        "resolves.json",
        "summary.json"
    ]

    for filename in artifact_files:
        os.rename(filename, os.path.join(destpath, filename))


def remove_old_results():
    path = os.path.join(benchmarking_dir, "artifacts")
    dirs = sorted(os.listdir(path))

    while len(dirs) > MAX_ARTIFACTS:
        shutil.rmtree(os.path.join(path, dirs[0]))
        dirs = dirs[1:]


def update_markdown():
    with open("summary.json") as f:
        summary = json.loads(f.read())

    columns = (
        "rez_version",
        "py_version",
        "platform",
        "cpu",
        "num_cpu",
        "median",
        "mean",
        "stddev"
    )

    def _tostr(value):
        if isinstance(value, float):
            return "%.02f" % value
        else:
            return str(value)

    md_table_line = "| " + " | ".join(_tostr(summary[x]) for x in columns) + " |"

    filepath = os.path.join(benchmarking_dir, "RESULTS.md")
    with open(filepath, "a") as f:
        f.write(md_table_line + '\n')


if __name__ == "__main__":
    update_markdown()
    store_result()
    remove_old_results()
