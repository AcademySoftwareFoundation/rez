from __future__ import print_function

import argparse
import json
import os
import os.path
import math
import subprocess
import sys
import time

# Default config settings, this has to be done before rez loads. This stops
# settings (such as resolve caching) affecting the benchmarking.
#
settings = {
    "memcached_uri": [],
    "package_filter": [],
    "package_orderers": [],
    "allow_unversioned_packages": False,
    "resource_caching_maxsize": -1,
    "cache_packages_path": None
}

for setting, value in settings.items():
    os.environ.pop("REZ_" + setting.upper(), None)
    os.environ["REZ_" + setting.upper() + "_JSON"] = json.dumps(value)

try:
    from rez.packages import iter_package_families
    from rez.resolved_context import ResolvedContext
    from rez.solver import SolverCallbackReturn

except ImportError:
    print(
        "Rez not present, you may need to invoke this script with rez-python "
        "depending on what you're doing."
    )


# globals
opts = None
out_dir = None
pkg_repo_dir = None
resolves_dir = None


def parse_args():
    parser = argparse.ArgumentParser("Rez benchmarker tool")

    parser.add_argument(
        "--out", metavar="RESULTS_DIR", default="results",
        help="Output dir (default: %(default)s)"
    )
    parser.add_argument(
        "--iterations", type=int, default=1, metavar="N",
        help="Run every resolve N times and take the average (default: %(default)s)"
    )
    parser.add_argument(
        "--histogram", action="store_true",
        help="Show an ASCII histogram of resolve times (in dir specified with --out)"
    )
    parser.add_argument(
        "--compare", metavar="RESULTS_DIR",
        help="Compare RESULTS_DIR to results specified via --out. Ie, if "
        "'mean_delta' is negative, then RESULTS_DIR resolves are faster on "
        "average than those in --out dir"
    )

    return parser.parse_args()


def load_packages():
    """Load all packages so loading time doesn't impact solve times
    """
    print("Warming package cache...")
    fams = list(iter_package_families(paths=[pkg_repo_dir]))

    for i, fam in enumerate(fams):
        sys.stdout.write("\n[%d/%d]" % (i + 1, len(fams)))

        for pkg in fam.iter_packages():
            pkg.validate_data()

            for var in pkg.iter_variants():
                pass  # just ensures variant objects are created and cached

            sys.stdout.write('.')
            sys.stdout.flush()

    print('')


def do_resolves():
    with open("./source_data/requests.json") as f:
        requests = json.loads(f.read())

    print("Performing %d resolves..." % len(requests))

    def callback(solver_state):
        sys.stdout.write('.')
        sys.stdout.flush()
        return (SolverCallbackReturn.keep_going, '')

    summaries = []
    t_start = time.time()

    for i, request_list in enumerate(requests):
        print("\n[%d/%d]" % (i + 1, len(requests)))
        print("Request: %s" % request_list)

        sys.stdout.write("Resolving")
        sys.stdout.flush()

        summary = {
            "request": request_list
        }

        # perform the resolve
        try:
            secs = 0.0

            for _ in range(opts.iterations):
                t = time.time()
                ctxt = ResolvedContext(
                    package_requests=request_list,
                    package_paths=[pkg_repo_dir],
                    add_implicit_packages=False,
                    callback=callback
                )
                secs += time.time() - t

            resolve_time = secs / opts.iterations
            print('\n')

            if ctxt.success:
                summary.update({
                    "status": "success",
                    "resolve_time": resolve_time,
                    "resolved_packages": [
                        os.path.relpath(x.uri, pkg_repo_dir)
                        for x in ctxt.resolved_packages
                    ]
                })
            else:
                summary.update({
                    "status": "failed",
                    "resolve_time": resolve_time
                })

        except Exception as e:
            print("\n%s" % str(e))

            summary.update({
                "status": "error",
                "error": str(e)
            })

        summaries.append(summary)

    # store resolve results to file
    with open(os.path.join(out_dir, "resolves.json"), 'w') as f:
        f.write(json.dumps(summaries, indent=2))

    # calculate, print results and store to file
    total_secs = time.time() - t_start
    successes = [x for x in summaries if x["status"] == "success"]
    errors = [x for x in summaries if x["status"] == "error"]
    fails = [x for x in summaries if x["status"] == "failed"]
    resolve_times = [
        x["resolve_time"] for x in summaries
        if x["status"] in ("success", "failed")
    ]
    n_resolve_times = len(resolve_times)

    stats = {
        "total_run_time": total_secs,
        "num_success_resolves": n_resolve_times,
        "num_error_resolves": len(errors),
        "num_failed_resolves": len(fails),
    }

    if resolve_times:
        resolve_times = sorted(resolve_times)
        median_resolve_time = resolve_times[n_resolve_times / 2]
        avg_resolve_time = sum(resolve_times) / float(n_resolve_times)
        min_resolve_time = min(resolve_times)
        max_resolve_time = max(resolve_times)
        stddev = math.sqrt(
            sum((x - avg_resolve_time) ** 2 for x in resolve_times) / n_resolve_times
        )

        stats.update({
            "median": median_resolve_time,
            "mean": avg_resolve_time,
            "min": min_resolve_time,
            "max": max_resolve_time,
            "stddev": stddev
        })

    print("\n\nRESULT:")
    stats_str = json.dumps(stats, indent=2)
    print(stats_str)

    with open(os.path.join(out_dir, "summary.json"), 'w') as f:
        f.write(stats_str)


def run_benchmark():
    if os.path.exists(out_dir):
        print(
            "Dir specified by --out (%s) must not exist" % out_dir,
            file=sys.stderr
        )
        sys.exit(1)

    os.mkdir(out_dir)
    print("Writing results to %s..." % out_dir)

    # extract package repo
    if os.path.exists(pkg_repo_dir):
        print("Using existing package repository at %s" % pkg_repo_dir)
    else:
        proc = subprocess.Popen(
            ["tar", "-xvf", "../source_data/packages.tar.gz"],
            cwd=out_dir
        )

        # wait for files to become visible on filesystem, sometimes they aren't
        # and all resolves fail
        time.sleep(5)

    load_packages()
    do_resolves()


def print_histogram():
    n_rows = 40
    n_columns = 40
    resolve_times = []
    buckets = [0] * n_rows

    with open(os.path.join(out_dir, "resolves.json")) as f:
        summaries = json.loads(f.read())

    for summary in summaries:
        if "resolve_time" not in summary:
            continue

        resolve_times.append(summary["resolve_time"])

    # place resolve times into buckets
    max_resolve_time = max(resolve_times)
    min_resolve_time = min(resolve_times)
    bucket_size = (max_resolve_time - min_resolve_time) / n_rows

    for resolve_time in resolve_times:
        i_bucket = int((resolve_time - min_resolve_time) / bucket_size)
        i_bucket = min(i_bucket, n_rows - 1)
        buckets[i_bucket] += 1

    # normalise buckets wrt max columns
    max_bucket = max(buckets)
    mult = n_columns / float(max_bucket)

    # print histogram
    start_t = min_resolve_time

    test_str = "[%.2f-%.2f]" % (max_resolve_time, max_resolve_time)
    max_left_column_w = len(test_str)

    for i in range(n_rows):
        bucket = buckets[i]
        end_t = start_t + bucket_size
        columns = int(bucket * mult)

        left_column = "[%.2f-%.2f]" % (start_t, end_t)
        n = max_left_column_w - len(left_column)
        left_column = (' ' * n) + left_column

        print("%s |%s" % (left_column, '#' * columns))

        start_t = end_t


def compare():
    out_dir2 = opts.compare
    mismatches = []

    with open(os.path.join(out_dir, "resolves.json")) as f:
        summaries1 = json.loads(f.read())
    with open(os.path.join(out_dir2, "resolves.json")) as f:
        summaries2 = json.loads(f.read())

    # list resolves that don't match
    for i, summary1 in enumerate(summaries1):
        try:
            summary2 = summaries2[i]
        except IndexError:
            continue

        resolve1 = summary1.get("resolved_packages")
        resolve2 = summary2.get("resolved_packages")

        if resolve1 != resolve2:
            print(
                "%s != %s" % (json.dumps(resolve1), json.dumps(resolve2)),
                file=sys.stderr
            )

    # show delta of summaries (avg solve time etc)
    with open(os.path.join(out_dir, "summary.json")) as f:
        summary1 = json.loads(f.read())
    with open(os.path.join(out_dir2, "summary.json")) as f:
        summary2 = json.loads(f.read())

    delta_summary = {}
    for field in ("max", "min", "mean", "median", "stddev"):
        delta = summary2[field] - summary1[field]
        pct = 100.0 * (delta / summary1[field])
        pct_str = "%.2f%%" % pct
        if not pct_str.startswith('-'):
            pct_str = '+' + pct_str

        delta_summary["%s_delta" % field] = (delta, pct_str)

    print(json.dumps(delta_summary, indent=2))


if __name__ == "__main__":
    opts = parse_args()

    # are we in the right place?
    if not os.path.exists("source_data/packages.tar.gz"):
        print("Run script in src/support/benchmarking dir", file=sys.stderr)

    out_dir = os.path.abspath(opts.out)
    pkg_repo_dir = os.path.join(out_dir, "packages")

    if opts.histogram:
        print_histogram()
    elif opts.compare:
        compare()
    else:
        run_benchmark()
