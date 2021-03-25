from __future__ import print_function
import os.path
import sys
import json


this_benchmark = {}
prev_benchmark = {}


def _load_benchmark(path):
    resolves_dict = {}

    with open(os.path.join(path, "resolves.json")) as f:
        resolves = json.loads(f.read())

    with open(os.path.join(path, "summary.json")) as f:
        summary = json.loads(f.read())

    # convert list of resolves into dict, for easier comparison
    for resolve in resolves:
        key = tuple(resolve["request"])
        resolves_dict[key] = {
            "status": resolve["status"],
            "resolved_packages": resolve.get("resolved_packages", [])
        }

    return {
        "resolves": resolves_dict,
        "solver_version": summary.get("rez_solver_version")
    }


def load_this_benchmark():
    this_benchmark.update(_load_benchmark("out"))


def load_prev_benchmark():
    # find most recent result
    artifacts_dir = os.path.join("metrics", "benchmarking", "artifacts")
    try:
        dirnames = os.listdir(artifacts_dir)
    except OSError:
        dirnames = []

    if not dirnames:
        return

    path = sorted(dirnames)[-1]
    prev_benchmark.update(_load_benchmark(path))


def compare_benchmarks():
    if not prev_benchmark:
        return  # no previous result to compare to

    # if solver version doesn't match, then don't bother comparing (see
    # solver.py:SOLVER_VERSION for more details)
    #
    if this_benchmark["solver_version"] != prev_benchmark["solver_version"]:
        print("Skipping benchmark comparison - solver versions differ")
        return

    for request, result in this_benchmark["resolves"].items():
        prev_result = prev_benchmark["resolves"].get(request)

        if prev_result and result != prev_result:
            info = {
                "request": request,
                "result": result,
                "prev_result": prev_result
            }

            print("RESOLVES DIFFER: %r" % info, file=sys.stderr)
            sys.exit(1)

    print("Success: Current resolves match previous resolves")


if __name__ == "__main__":
    load_this_benchmark()
    load_prev_benchmark()
    compare_benchmarks()
