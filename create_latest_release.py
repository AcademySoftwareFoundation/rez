"""
Takes the latest entry in CHANGELOG.md and creates the matching release notes
on GitHub (https://github.com/nerdvegas/rez/releases).
"""

from getpass import getpass
import pipes
import pprint
import re
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
    pr_regex = re.compile("[0-9]+")

    with open("CHANGELOG.md") as f:
        for line in f.readlines():
            parts = line.split()

            if parts and parts[0] == "##":
                if result.get("version"):
                    result["body"] = ''.join(body_lines).strip()
                    return result

                # eg: ## 2.26.4 [[#562](https://github.com/nerdvegas/rez/pull/562)] Fixed Regression in 2.24.0
                result["version"] = parts[1]
                result["pr_num"] = int(pr_regex.findall(parts[2])[0])
                result["name"] = ' '.join(parts[3:])

            elif result.get("version"):
                body_lines.append(line)


if __name__ == "__main__":
    # check that we're on master
    branch = run_proc("git", "branch", "--contains").split()[-1]
    if branch != "master":
        print >> sys.stderr, "Must be run from master"
        sys.exit(1)

    # get current tag
    latest_tag = run_proc("git", "describe", "--tags")

    # see if latest release already matches tag
    response = requests.get(get_url("releases/latest"))
    response.raise_for_status()
    latest_release_tag = response.json()["tag_name"]

    if latest_release_tag == latest_tag:
        print >> sys.stderr, "Release for %s already exists" % latest_tag
        sys.exit(1)

    # parse latest release out of changelog
    changelog = parse_topmost_changelog()

    # perform some modifications to the release info
    tag_name = changelog["version"]
    name = "{version}: {name}".format(**changelog)

    pr_url = "https://github.com/nerdvegas/rez/pull/" + str(changelog["pr_num"])
    body = "#### Release PR:\n\n" + pr_url + "\n\n" + changelog["body"]

    data = dict(
        tag_name=tag_name,
        name=name,
        body=body
    )
    print(pprint.pformat(data))

    # create the release on github
    response = requests.post(
        get_url("releases"),
        json=data,
        headers=default_headers
    )

    response.raise_for_status()
