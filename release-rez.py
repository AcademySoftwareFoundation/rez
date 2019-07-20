"""
Release a new version of rez.

Read RELEASE.md before using this utility.
"""
import argparse
import os
from pipes import quote
import subprocess
import sys

try:
    import requests
except ImportError:
    sys.stderr.write("Requires python requests module.\n")
    sys.exit(1)

source_path = os.path.dirname(os.path.realpath(__file__))
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version


github_username = os.getenv("GITHUB_USER")
github_password = os.getenv("GITHUB_PASSWORD")


def run_command(*nargs):
    print("RUNNING: %s" % ' '.join(map(quote, nargs)))
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    out, _ = proc.communicate()

    if proc.returncode:
        sys.stderr.write("Aborting, failed with exit code %d.\n" % proc.returncode)
        sys.exit(proc.returncode)

    return out.strip()


def get_github_url(endpoint=None):
    global github_username, github_password

    github_url = "https://{username}:{password}@api.github.com/repos/nerdvegas/rez/"

    if github_username is None or github_password is None:
        github_username = raw_input("Github username: ").strip()
        github_password = getpass("Github password: ").strip()

    url = github_url.format(username=github_username, password=github_password)

    if endpoint:
        url += endpoint
    return url


def parse_topmost_changelog():
    result = {}
    body_lines = []

    with open("CHANGELOG.md") as f:
        for line in f.readlines():
            parts = line.split()

            # eg: ## 2.38.0 (2019-07-20)
            if parts and parts[0] == "##":
                if result.get("version"):
                    result["body"] = ''.join(body_lines).strip()
                    return result

                result["version"] = parts[1]
                result["name"] = result["version"] + ' '.join(parts[2:])

            elif result.get("version"):
                body_lines.append(line)

    # should never get here
    assert False


def check_on_master():
    branch = run_command("git", "branch", "--contains").split()[-1]

    if branch != "master":
        sys.stderr.write("Must be run from master.\n")
        sys.exit(1)


def push_codebase():
    run_command("git", "push")


def create_and_push_tag():
    run_command("git", "tag", _rez_version)
    run_command("git", "push", "origin", _rez_version)


def create_github_release_notes():
    # check if latest release notes already match current version
    response = requests.get(get_github_url("releases/latest"))
    response.raise_for_status()
    latest_release_tag = response.json()["tag_name"]

    if latest_release_tag == _rez_version:
        sys.stderr.write("Release for %s already exists.\n" % latest_tag)
        sys.exit(1)

    # parse latest release out of changelog
    changelog = parse_topmost_changelog()

    tag_name = changelog["version"]
    if tag_name != _rez_version:
        sys.stderr.write(
            "Latest entry in changelog (%s) doesn't match latest tag (%s).\n"
            % (tag_name, latest_tag)
        )
        sys.exit(1)

    data = dict(
        tag_name=_rez_version,
        name=changelog["name"],
        body=changelog["body"]
    )

    # create the release on github
    response = requests.post(
        get_github_url("releases"),
        json=data,
        headers={"Content-Type": "application/json"}
    )

    response.raise_for_status()
    url = "https://github.com/nerdvegas/rez/releases/tag/" + _rez_version
    print "Created release notes: " + url


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step", choices=("push", "tag", "release_notes"),
        help="Just run one step of the release process")

    opts = parser.parse_args()

    print("Releasing rez-%s..." % _rez_version)

    def doit(step):
        return (opts.step is None) or (step == opts.step)

    check_on_master()

    if doit("push"):
        push_codebase()

    if doit("tag"):
        create_and_push_tag()

    if doit("release_notes"):
        create_github_release_notes()
