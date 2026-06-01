# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Release a new version of rez.

Read RELEASE.md before using this utility.
"""
import argparse
import os
from datetime import date
from shlex import quote
import subprocess
import sys
import re

try:
    import requests
except ImportError:
    sys.stderr.write("Requires python requests module.\n")
    sys.exit(1)

source_path = os.path.dirname(os.path.realpath(__file__))
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version


def get_github_repo_owner():
    out = subprocess.check_output(["git", "remote", "-v"], text=True)

    # The output looks like this:
    # chadrik git@github.com:chadrik/rez (fetch)
    # chadrik git@github.com:chadrik/rez (push)
    # origin  git@github.com:JeanChristopheMorinPerso/rez.git (fetch)
    # origin  git@github.com:JeanChristopheMorinPerso/rez.git (push)
    # upstream        git@github.com:AcademySoftwareFoundation/rez.git (fetch)
    # upstream        git@github.com:AcademySoftwareFoundation/rez.git (push)

    remotes: list[tuple[str, str]] = []
    for line in out.splitlines():
        remotes.append(line.split()[0:2])

    if len(set([remote[1] for remote in remotes])) > 1:
        print(
            "More than one remote are configured. The script doesn't support multiple remotes.",
            file=sys.stderr,
        )
        sys.exit(1)

    remote = remotes[0]
    if remote[0] != "origin":
        print(
            f"Rename name is {remote[0]!r}. Was expecting 'origin'",
            file=sys.stderr,
        )

    return remote[1].split(":")[-1].split("/", maxsplit=1)[0]


_repo_owner = get_github_repo_owner()
github_baseurl = "github.com/repos/%s/rez" % _repo_owner
github_baseurl2 = "github.com/%s/rez" % _repo_owner
verbose = False

# https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line
# requires 'public_repo' access
#
github_token = os.environ["GITHUB_RELEASE_REZ_TOKEN"]


def run_command(*nargs):
    if verbose:
        print("RUNNING: %s" % ' '.join(map(quote, nargs)))

    proc = subprocess.Popen(nargs, stdout=subprocess.PIPE, text=True)
    out, _ = proc.communicate()

    if proc.returncode:
        sys.stderr.write("Aborting, failed with exit code %d.\n" % proc.returncode)
        sys.exit(proc.returncode)

    return out.strip()


def github_request(method, endpoint, headers=None, **kwargs):
    url = "https://api.%s/%s" % (github_baseurl, endpoint)
    headers = (headers or {}).copy()
    headers["Authorization"] = "token " + github_token
    return requests.request(method, url, headers=headers, **kwargs)


def parse_topmost_changelog():
    result = {}
    body_lines = []

    with open("CHANGELOG.md") as f:
        for line in f.readlines():
            parts = line.split()

            # eg: ## 2.38.0 (2019-07-20)
            if parts and parts[0] == "##":
                if result.get("version"):
                    for index, line in enumerate(body_lines):
                        # Replace the user URL to a github handle. This will allow GH to properly
                        # attribute and tag all contributors on the release page.
                        # [user](https://github.com/user) > @user
                        line = re.sub(r"\[([^\]]+)\]\(https://github\.com/\1\)", r"@\1", line)
                        # Now replace all links to rez GH issues and PR with `#<number>`.
                        # This is purely cosmetic. It at least makes the output cleaner.
                        # [\#1234](https://github.com/AcademySoftwareFoundation/rez/pull/1234) > #1234.
                        line = re.sub(r'\[\\#(\d+)\]\(https://github\.com/AcademySoftwareFoundation/rez/(pull|issues)/\1\)', r'#\1', line)
                        body_lines[index] = line

                    result["body"] = ''.join(body_lines).strip()
                    return result

                # The version in our changelog is prefixed with `v`. Get rid of that.
                result["version"] = parts[1].lstrip("v")
                result["name"] = ' '.join(parts[1:]).lstrip("v")

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


def check_on_main():
    branch = run_command("git", "branch", "--contains").split()[-1]

    if branch != "main":
        sys.stderr.write("Must be run from the 'main' branch.\n")
        sys.exit(1)


def push_codebase():
    run_command("git", "push")


def create_and_push_tag():
    run_command("git", "tag", _rez_version)
    run_command("git", "push", "origin", _rez_version)


def create_github_release_notes():
    # check if latest release notes already match current version
    response = github_request("get", "releases/latest")
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
    response = github_request(
        "post",
        "releases",
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
        response = github_request(
            "get",
            "issues/%d" % issue_num,
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
        "## v%s (%d-%02d-%02d)" %
        (_rez_version, today.year, today.month, today.day)
    )

    print(
        "[Source](https://%s/tree/%s) | [Diff](https://%s/compare/%s...%s)" %
        (github_baseurl2, _rez_version, github_baseurl2, previous_version, _rez_version)
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
        "-c", "--changelog", nargs='*', metavar="ISSUE", type=int,
        help="Generate changelog entry to be added to CHANGELOG.md")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose mode")

    opts = parser.parse_args()
    verbose = opts.verbose

    if opts.changelog is not None:
        issue_nums = opts.changelog
        generate_changelog_entry(issue_nums)
        sys.exit(0)

    print("Releasing rez-%s..." % _rez_version)

    def doit(step):
        return (opts.step is None) or (step == opts.step)

    check_on_main()

    if doit("push"):
        push_codebase()

    if doit("tag"):
        create_and_push_tag()

    if doit("release_notes"):
        create_github_release_notes()
