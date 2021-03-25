'''
Run a benchmarking suite for runtime resolves.
'''
from __future__ import print_function

import json
import os
import os.path
import math
import subprocess
import platform
import sys
import time


# globals
opts = None
out_dir = None
pkg_repo_dir = None


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--out", metavar="RESULTS_DIR", default="out",
        help="Output dir (default: %(default)s)"
    )
    parser.add_argument(
        "--iterations", type=int, default=1, metavar="N",
        help="Run every resolve N times and take the average (default: %(default)s)"
    )
    parser.add_argument(
        "--histogram", action="store_true",
        help="Show an ASCII histogram of resolve times (from results in --out)"
    )
    parser.add_argument(
        "--compare", metavar="RESULTS_DIR",
        help="Compare RESULTS_DIR to results specified via --out. Ie, if "
        "'mean_delta' is negative, then RESULTS_DIR resolves are faster on "
        "average than those in --out dir"
    )


def load_packages():
    """Load all packages so loading time doesn't impact solve times
    """
    from rez.packages import iter_package_families

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


def get_system_info():
    """Get system info that might affect resolve time.
    """
    from rez import __version__
    from rez.utils.execution import Popen
    from rez.solver import SOLVER_VERSION

    info = {
        "rez_version": __version__,
        "rez_solver_version": SOLVER_VERSION,
        "py_version": "%d.%d" % sys.version_info[:2],
        "platform": platform.platform()
    }

    # this may only work on linux, but that's ok - the important thing is that
    # it works in the benchmark workflow, and we run that on linux only
    #
    try:
        proc = Popen(
            ["cat", "/proc/cpuinfo"],
            stdout=subprocess.PIPE,
            text=True
        )
        out, _ = proc.communicate()

        if proc.returncode == 0:
            # parse output, lines are like 'field : value'
            fields = {}
            for line in out.strip().split('\n'):
                if ':' not in line:
                    continue

                parts = line.strip().split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip()
                fields[key] = value

            # get the bits we care about
            info["num_cpu"] = int(fields["processor"]) + 1
            info["cpu"] = fields["model name"]
    except:
        pass

    return info


def do_resolves():
    from rez import module_root_path
    from rez.resolved_context import ResolvedContext
    from rez.solver import SolverCallbackReturn

    filepath = os.path.join(module_root_path, "data", "benchmarking", "requests.json")
    with open(filepath) as f:
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

            for _ in range(_opts.iterations):
                t = time.time()
                ctxt = ResolvedContext(
                    package_requests=request_list,
                    package_paths=[pkg_repo_dir],
                    add_implicit_packages=False,
                    callback=callback
                )
                secs += time.time() - t

            resolve_time = secs / _opts.iterations
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

    stats.update(get_system_info())

    if resolve_times:
        resolve_times = sorted(resolve_times)
        median_resolve_time = resolve_times[n_resolve_times // 2]
        avg_resolve_time = sum(resolve_times) / float(n_resolve_times)
        min_resolve_time = min(resolve_times)
        max_resolve_time = max(resolve_times)
        stddev = math.sqrt(
            sum((x - avg_resolve_time) ** 2 for x in resolve_times) / float(n_resolve_times)
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
    from rez import module_root_path
    from rez.utils.execution import Popen

    if os.path.exists(out_dir):
        print(
            "Dir specified by --out (%s) must not exist" % out_dir,
            file=sys.stderr
        )
        sys.exit(1)

    os.mkdir(out_dir)
    print("Writing results to %s..." % out_dir)

    # extract package repo
    filepath = os.path.join(module_root_path, "data", "benchmarking", "packages.tar.gz")
    proc = Popen(
        ["tar", "-xf", filepath],
        cwd=out_dir
    )
    proc.wait()

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
    out_dir2 = _opts.compare

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

        request = summary1.get("request")
        resolve1 = summary1.get("resolved_packages")
        resolve2 = summary2.get("resolved_packages")

        if resolve1 != resolve2:
            print(
                "MISMATCHING RESULT (#%d):\n"
                "REQUEST: %r\n"
                "RESOLVE FROM %s: %r\n"
                "RESOLVE FROM %s: %r"
                % (i, request, out_dir, resolve1, out_dir2, resolve2),
                file=sys.stderr
            )
            sys.exit(1)

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


def command(opts, parser, extra_arg_groups=None):
    global _opts
    global out_dir
    global pkg_repo_dir

    _opts = opts
    out_dir = os.path.abspath(opts.out)
    pkg_repo_dir = os.path.join(out_dir, "packages")

    if opts.histogram:
        print_histogram()
    elif opts.compare:
        compare()
    else:
        run_benchmark()
