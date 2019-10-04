"""
Release a new version of rez.

Read RELEASE.md before using this utility.
"""
from __future__ import print_function
import argparse
import os
from datetime import date
from getpass import getpass
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


github_baseurl = "github.com/repos/nerdvegas/rez"
github_username = os.getenv("GITHUB_USERNAME")
github_password = os.getenv("GITHUB_PASSWORD")
verbose = False


def run_command(*nargs):
    if verbose:
        print("RUNNING: %s" % ' '.join(map(quote, nargs)))

    proc = subprocess.Popen(nargs, stdout=subprocess.PIPE)
    out, _ = proc.communicate()

    if proc.returncode:
        sys.stderr.write("Aborting, failed with exit code %d.\n" % proc.returncode)
        sys.exit(proc.returncode)

    return out.strip()


def get_github_url(endpoint=None):
    global github_username, github_password

    github_url = "https://{username}:{password}@api.%s/" % github_baseurl

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
                result["name"] = ' '.join(parts[1:])

            elif result.get("version"):
                # GitHub seems to treat separate lines in the md as line breaks,
                # rather than keeping them in the same paragraph as a typical
                # md renderer would. So patch that up here.
                #
                br_chars = ('*', '-', '#', '[')

                if body_lines and \
                        body_lines[-1].strip() and \
                        body_lines[-1][0] not in br_chars and \
                        line.strip() and \
                        line[0] not in br_chars:
                    # append to previous line
                    body_lines[-1] = body_lines[-1].rstrip() + ' ' + line
                else:
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
        sys.stderr.write("Release for %s already exists.\n" % _rez_version)
        sys.exit(1)

    # parse latest release out of changelog
    changelog = parse_topmost_changelog()

    tag_name = changelog["version"]
    if tag_name != _rez_version:
        sys.stderr.write(
            "Latest entry in changelog (%s) doesn't match current version (%s).\n"
            % (tag_name, _rez_version)
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
    url = "https://%s/releases/tag/%s" % (github_baseurl, _rez_version)
    print("Created release notes: " + url)


def generate_changelog_entry(issue_nums):
    # parse previous release out of changelog
    changelog = parse_topmost_changelog()

    previous_version = changelog["version"]
    if previous_version == _rez_version:
        sys.stderr.write(
            "Latest entry in changelog (%s) matches current version (%s).\n"
            % (previous_version, _rez_version)
        )
        sys.exit(1)

    # get issues and PRs from cli
    pr_lines = []
    issue_lines = []

    for issue_num in sorted(issue_nums):
        # note that 'issues' endpoint also returns PRs
        response = requests.get(
            get_github_url("issues/%d" % issue_num),
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 404:
            sys.stderr.write("Issue/PR does not exist: %d\n" % issue_num)
            sys.exit(1)

        response.raise_for_status()

        data = response.json()
        url = data["html_url"]
        user = data["user"]
        title = data["title"]
        title = title.lstrip('-')

        if "pull_request" in data:
            pr_lines.append(
                "- %s [\\#%d](%s) ([%s](%s))"
                % (title, issue_num, url, user["login"], user["html_url"])
            )
        else:
            # issue
            issue_lines.append(
                "- %s [\\#%d](%s)"
                % (title, issue_num, url)
            )

    # print title section
    today = date.today()
    print(
        "## %s (%d-%02d-%02d)" %
        (_rez_version, today.year, today.month, today.day)
    )

    print(
        "[Source](https://%s/tree/%s) | [Diff](https://%s/compare/%s...%s)" %
        (github_baseurl, _rez_version, github_baseurl, previous_version, _rez_version)
    )

    print("")

    # print PRs and issues
    if pr_lines:
        print(
            "**Merged pull requests:**\n\n" +
            "\n".join(pr_lines)
        )

    if issue_lines:
        if pr_lines:
            print("")
        print(
            "**Closed issues:**\n\n" +
            "\n".join(issue_lines)
        )

    print("")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--step", choices=("push", "tag", "release_notes"),
        help="Just run one step of the release process")
    parser.add_argument(
        "-c", "--changelog", nargs='+', metavar="ISSUE", type=int,
        help="Generate changelog entry to be added to CHANGELOG.md")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose mode")

    opts = parser.parse_args()
    verbose = opts.verbose

    if opts.changelog:
        issue_nums = opts.changelog
        generate_changelog_entry(issue_nums)
        sys.exit(0)

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
