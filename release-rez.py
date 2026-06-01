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
repo_name = f"{_repo_owner}/rez"
github_baseurl = "github.com/%s" % repo_name
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
    url = f"https://api.github.com/repos/{repo_name}/{endpoint}"
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


def create_and_push_tag():
    run_command("git", "tag", _rez_version)
    run_command("git", "push", "origin", _rez_version)


def create_github_release():
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

    print("\033[1mTag\033[0m:", data["tag_name"])
    print("\033[1mName\033[0m:", data["name"])
    print("\033[1mBody\033[0m:")
    print(data["body"])
    print()
    answer = None
    while answer is None:
        answer_ = input("Does this look good? [y/n]")
        if answer_.lower() not in ["y", "n"]:
            continue

        answer = answer_

    if answer == "n":
        print("Aborting release!")
        return

    print("Proceeding with the release")

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


def generate_changelog_entry():
    # parse previous release out of changelog
    changelog = parse_topmost_changelog()

    previous_version = changelog["version"]
    if previous_version == _rez_version:
        sys.stderr.write(
            "Latest entry in changelog (%s) matches current version (%s).\n"
            % (previous_version, _rez_version)
        )
        sys.exit(1)

    # Discover PRs from commits between the previous tag and HEAD.
    # For each commit, ask GitHub which PR(s) contain it, and merge the
    # resulting PR numbers into any issue/PR numbers passed in by the caller.
    discovered_prs = set()

    response = github_request("get", "compare/%s...HEAD" % previous_version)
    response.raise_for_status()
    response_content = response.json()
    commits = response_content.get("commits", [])
    if len(commits) < response_content.get("total_commits"):
        raise ValueError("List of commits is paginated")

    for commit in commits:
        sha = commit["sha"]
        pr_response = github_request("get", "commits/%s/pulls" % sha)
        pr_response.raise_for_status()
        for pr in pr_response.json():
            discovered_prs.add(pr["number"])

    if verbose:
        sys.stderr.write(
            "Discovered %d PR(s) from %d commit(s) between %s and HEAD: %s\n"
            % (len(discovered_prs), len(commits), previous_version,
               sorted(discovered_prs))
        )

    # get issues and PRs from cli
    pr_lines = []
    issue_lines = []

    for issue_num in sorted(discovered_prs):
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
    parser.add_argument("--dry-run", help="Don't run any destructive actions")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose mode",
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    changelog_parser = subparsers.add_parser(
        "changelog",
        help="Generate the changelog entry and print to stdout"
    )

    subparsers.add_parser(
        "tag",
        help="Tag and push the tag"
    )

    subparsers.add_parser(
        "release",
        help="Create the release"
    )

    opts = parser.parse_args()
    verbose = opts.verbose

    command_map = {
        "changelog": generate_changelog_entry,
        "tag": create_and_push_tag,
        "release": create_github_release,
    }

    check_on_main()

    command = command_map.get(opts.subcommand)
    if command:
        command()
    else:
        raise RuntimeError(f"Add {opts.subcommand!r} to command_map")
