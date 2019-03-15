import argparse
from getpass import getpass
import pipes
import pprint
import subprocess
import sys

import requests


github_url = "https://{username}:{password}@api.github.com/repos/nerdvegas/rez/"
username = None
password = None

default_headers = {
    "Content-Type": "application/json",
}


def get_url(endpoint=None):
    global username, password

    if username is None:
        username = raw_input("Github username: ").strip()
        password = getpass("Github password: ").strip()

    url = github_url.format(username=username, password=password)

    if endpoint:
        url += endpoint

    return url


def run_proc(*nargs):
    cmd = ' '.join(map(pipes.quote, nargs))
    print("Running: %s" % cmd)

    proc = subprocess.Popen(nargs, stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode:
        sys.exit(proc.returncode)

    return out.strip()


def parse_topmost_changelog():
    result = {}
    body_lines = []

    with open("CHANGELOG.md") as f:
        for line in f.readlines():
            parts = line.split()

            # eg: ## [2.27.0](https://github.com/nerdvegas/rez/tree/2.27.0) (2019-01-24)
            if parts and parts[0] == "##":
                if result.get("version"):
                    result["body"] = ''.join(body_lines).strip()
                    return result

                result["version"] = parts[1].split(']')[0].split('[')[-1]
                result["name"] = result["version"] + ' ' + parts[-1]

            elif result.get("version"):
                body_lines.append(line)


def create_changelog_entry(opts):
    """
    Requires github_changelog_generator util:
    https://github.com/github-changelog-generator/github-changelog-generator
    """

    # get most recent tag - we only want to generate the new changelog up til there
    changelog = parse_topmost_changelog()
    tag_name = changelog["version"]

    run_proc(
        "github_changelog_generator",
        "--since-tag=" + tag_name,
        "--output=LATEST_CHANGELOG.md"
    )


def create_release_notes():
    # check that we're on master
    branch = run_proc("git", "branch", "--contains").split()[-1]
    if branch != "master":
        print >> sys.stderr, "Must be run from master"
        sys.exit(1)

    # get current tag
    latest_tag = run_proc("git", "describe", "--tags", "--abbrev=0")

    # see if latest release already matches tag
    response = requests.get(get_url("releases/latest"))
    response.raise_for_status()
    latest_release_tag = response.json()["tag_name"]

    if latest_release_tag == latest_tag:
        print >> sys.stderr, "Release for %s already exists" % latest_tag
        sys.exit(1)

    # parse latest release out of changelog
    changelog = parse_topmost_changelog()

    tag_name = changelog["version"]
    if tag_name != latest_tag:
        print >> sys.stderr, (
            "Latest entry in changelog (%s) doesn't match latest tag (%s)"
            % (tag_name, latest_tag)
        )
        sys.exit(1)

    data = dict(
        tag_name=tag_name,
        name=changelog["name"],
        body=changelog["body"]
    )

    print(pprint.pformat(data))

    # create the release on github
    response = requests.post(
        get_url("releases"),
        json=data,
        headers=default_headers
    )

    response.raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser("create-release-notes")
    subparser.set_defaults(func=create_release_notes)

    subparser = subparsers.add_parser("create-changelog-entry")
    subparser.set_defaults(func=create_changelog_entry)

    opts = parser.parse_args()
    opts.func(opts)
