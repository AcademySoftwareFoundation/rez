from __future__ import print_function
import os
import os.path
import json
import sys
import shutil
import time
import subprocess

src_path = os.path.join(os.getcwd(), "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version  # noqa


# max number of result artifacts to store
MAX_ARTIFACTS = 100

# behave differently outside of github actions, for testing
in_gh = (os.getenv("GITHUB_ACTIONS") == "true")

benchmarking_dir = os.path.join("metrics", "benchmarking")
artifacts_dir = os.path.join(benchmarking_dir, "artifacts")
gnuplot_error = None

results_md_template = \
"""
# Benchmarking Results

This document contains historical benchmarking results. These measure the speed
of resolution of a list of predetermined requests. Do **NOT** change this file
by hand; the 'benchmark' Github workflow does this automatically.

{gnuplot_image}

| Rez | Python | Platform | CPU | #CPU | Median | Mean | StdDev |
|-----|--------|----------|-----|------|--------|------|--------|
{rows}
"""  # noqa

gnuplot_script = \
"""
set xtics rotate
set term png
set border 1
set output 'solvetimes.png'
plot "solvetimes.dat" using 2:xtic(1) title 'Mean' with lines, \
  "solvetimes.dat" using 3:xtic(1) title 'Median' with lines lc "gray", \
  "solvetimes.dat" using 2:4 title 'Stddev' with errorbars
"""  # noqa


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

    destpath = os.path.join(artifacts_dir, destdir)
    if os.path.exists(destpath):
        return

    os.makedirs(destpath)

    # take the files that the artifact download created, and move them into
    # the versioned directory. Note that the GH workflow is currently running
    # with cwd=./src, but these artifacts are in the dir above
    #
    artifact_files = [
        "resolves.json",
        "summary.json"
    ]

    results_path = os.path.dirname(os.getcwd())

    for filename in artifact_files:
        os.rename(
            os.path.join(results_path, filename),
            os.path.join(destpath, filename)
        )


def remove_old_results():
    path = os.path.join(benchmarking_dir, "artifacts")
    dirs = sorted(os.listdir(path))

    while len(dirs) > MAX_ARTIFACTS:
        shutil.rmtree(os.path.join(path, dirs[0]))
        dirs = dirs[1:]


def generate_gnuplot():
    global gnuplot_error

    # detect latest python in benchmark results
    pyvers = set()
    for summary in _iter_summaries():
        pyver = summary["py_version"]
        pyvers.add(tuple(int(x) for x in pyver.split('.')))
    latest_pyver = '.'.join(str(x) for x in max(pyvers))

    # generate data file for gnuplot to consume. Just use results from latest
    # python
    #
    dat_filepath = os.path.join(benchmarking_dir, "solvetimes.dat")
    with open(dat_filepath, 'w') as f:
        for summary in _iter_summaries():
            if summary["py_version"] != latest_pyver:
                continue

            f.write(
                "%s-py%s %f %f %f\n"
                % (
                    summary["rez_version"],
                    summary["py_version"],
                    summary["mean"],
                    summary["median"],
                    summary["stddev"]
                )
            )

    # create gnuplot script
    script_filepath = os.path.join(benchmarking_dir, "solvetimes.gnuplot")
    with open(script_filepath, 'w') as f:
        f.write(gnuplot_script)

    # run gnuplot
    try:
        subprocess.check_output(
            ["gnuplot", "./solvetimes.gnuplot"],
            cwd=benchmarking_dir
        )
    except Exception as e:
        gnuplot_error = str(e)
    finally:
        os.remove(dat_filepath)
        os.remove(script_filepath)


def update_markdown():
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

    md_lines = []
    variables = {}

    # generate table
    for summary in _iter_summaries():
        line = "| " + " | ".join(_tostr(summary[x]) for x in columns) + " |"
        md_lines.append(line)

    variables["rows"] = '\n'.join(md_lines)

    # insert previously generated gnuplot image
    if os.path.exists(os.path.join(benchmarking_dir, "solvetimes.png")):
        variables["gnuplot_image"] = (
            '<p align="center"><img src="solvetimes.png" /></p>'
        )
    else:
        variables["gnuplot_image"] = (
            "Gnuplot failed:\n```%s```" % gnuplot_error
        )

    # generate and write out markdown
    results_md = results_md_template.format(**variables)

    md_filepath = os.path.join(benchmarking_dir, "RESULTS.md")
    with open(md_filepath, "w") as f:
        f.write(results_md)


def _iter_summaries():
    def sort_fn(path):
        # sort by rez version, then py version
        parts = path.split('-')
        vers_str = parts[-1] + '.' + parts[-2]
        return [int(x) for x in vers_str.split('.')]

    for name in sorted(os.listdir(artifacts_dir), key=sort_fn):
        filepath = os.path.join(artifacts_dir, name, "summary.json")
        with open(filepath) as f:
            yield json.loads(f.read())


if __name__ == "__main__":
    if in_gh:
        store_result()
        remove_old_results()

    generate_gnuplot()
    update_markdown()
