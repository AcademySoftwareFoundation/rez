from __future__ import print_function
import os
import os.path
import json
import sys
import time

src_path = os.path.join(os.getcwd(), "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version  # noqa


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

    destpath = os.path.join("metrics", "benchmarking", "artifacts", destdir)
    if os.path.exists(destpath):
        return

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


def update_markdown():
    filepath = os.path.join("metrics", "benchmarking", "summary.json")
    with open(filepath) as f:
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

    md_table_line = "| ".join(str(summary[x]) for x in columns) + " |"

    filepath = os.path.join("metrics", "benchmarking", "RESULTS.md")
    with open(filepath, "a") as f:
        f.write(md_table_line + '\n')


if __name__ == "__main__":
    update_markdown()
    store_result()
