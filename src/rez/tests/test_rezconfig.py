# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

"""Tests for requirements specific to the default rezconfig."""

from __future__ import annotations

import os
import os.path
import re
import shutil
import subprocess
from typing import Optional
import unittest

from rez import rezconfig
from rez.utils.docs import parse_documented_settings


_REZCONFIG_BASELINE_ENV = "__REZ_SELFTEST_REZCONFIG_BASELINE"
_VERSIONADDED_RE = re.compile(
    r"^\s*\.\.\s+versionadded::\s+\S+\s*$"
)


def _new_settings_without_versionadded(baseline_source, current_source):
    baseline_settings = {
        setting.name: setting
        for setting in parse_documented_settings(baseline_source)
    }
    current_settings = {
        setting.name: setting
        for setting in parse_documented_settings(current_source)
    }
    new_settings = set(current_settings) - set(baseline_settings)
    return [
        name for name in sorted(
            new_settings,
            key=lambda name: current_settings[name].lineno,
        )
        if not any(
            _VERSIONADDED_RE.match(line)
            for line in current_settings[name].comment_lines
        )
    ]


def _git_output(*args):
    return subprocess.check_output(
        ["git"] + list(args),
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()


def _rezconfig_baseline(
    repo_root: str,
    requested_baseline: Optional[str],
) -> str:
    """Return the Git revision used to detect newly added settings.

    CI supplies an explicit event revision so pull requests and pushes are
    compared with the exact commit that preceded them. For local runs, compare
    the default branch with its parent, and compare feature branches with their
    merge base against origin's default branch.

    A detached HEAD is normal in CI and has no branch name. If it points at the
    default branch tip, treat it as the default branch; otherwise use the merge
    base behavior. Unexpected Git failures are intentionally allowed to
    propagate to the caller.
    """
    if requested_baseline:
        return requested_baseline

    # Resolve origin's default branch symbolically rather than assuming a name
    # such as "main" or "master".
    default_ref = _git_output(
        "-C", repo_root, "symbolic-ref", "refs/remotes/origin/HEAD"
    )
    default_branch = default_ref.replace("refs/remotes/origin/", "", 1)
    default_commit = _git_output("-C", repo_root, "rev-parse", default_ref)
    head_commit = _git_output("-C", repo_root, "rev-parse", "HEAD")
    # Unlike `git symbolic-ref`, this succeeds with an empty result for a
    # detached HEAD, so a legitimate checkout is not handled as an error.
    branch = _git_output("-C", repo_root, "branch", "--show-current")

    if branch == default_branch or (not branch and head_commit == default_commit):
        return "HEAD^"
    return _git_output("-C", repo_root, "merge-base", "HEAD", default_ref)


class TestRezConfigDocumentation(unittest.TestCase):
    """Validate that the rezconfig file follow the project's conventions.

    The goal is to catch common mistakes when modifying the rezconfig file.
    That file is use as the default settings but it's also used to generate
    the settings documentation and it must follow some rules.
    """

    def test_documented_settings_belong_to_a_section(self) -> None:
        """Ensure that all settings are declared in a section"""

        with open(rezconfig.__file__, encoding="utf-8") as stream:
            settings = parse_documented_settings(stream.read())

        sectionless = [
            setting.name for setting in settings if setting.section is None
        ]
        if sectionless:
            count = len(sectionless)
            self.fail(
                "Found %d %s in rezconfig outside a documentation section:"
                "\n\n%s\n\nDocumented rezconfig settings must be placed "
                "under a section that follows the style of existing sections."
                % (
                    count,
                    "setting" if count == 1 else "settings",
                    "\n".join("- %s" % name for name in sectionless),
                )
            )

    def test_documented_settings_have_docs(self) -> None:
        """Ensure that all settings have documentation"""

        with open(rezconfig.__file__, encoding="utf-8") as stream:
            settings = parse_documented_settings(stream.read())

        missing = [
            setting.name
            for setting in settings
            if not any(
                line.strip() and not _VERSIONADDED_RE.match(line)
                for line in setting.comment_lines
            )
        ]
        if missing:
            count = len(missing)
            self.fail(
                "Found %d %s in rezconfig that %s missing documentation:"
                "\n\n%s\n\nDocumented rezconfig settings must include a "
                "preceding documentation comment that must follow the style "
                "of existing settings."
                % (
                    count,
                    "setting" if count == 1 else "settings",
                    "is" if count == 1 else "are",
                    "\n".join("- %s" % name for name in missing),
                )
            )

    def test_new_documented_settings_have_versionadded(self) -> None:
        """Ensure that new settings have a versionadded sphinx directive"""

        if shutil.which("git") is None:
            self.skipTest("Git executable is unavailable")

        requested_baseline = os.getenv(_REZCONFIG_BASELINE_ENV)
        try:
            repo_root = _git_output("rev-parse", "--show-toplevel")
            baseline = _rezconfig_baseline(repo_root, requested_baseline)
            path = os.path.relpath(rezconfig.__file__, repo_root).replace(os.sep, "/")
            with open(rezconfig.__file__, encoding="utf-8") as stream:
                current_source = stream.read()
            baseline_source = _git_output(
                "-C", repo_root, "show", "%s:%s" % (baseline, path)
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            reason = "Git repository or usable rezconfig history is unavailable"
            if requested_baseline:
                self.fail("%s for baseline %r: %s" % (
                    reason, requested_baseline, exc
                ))
            self.skipTest("%s: %s" % (reason, exc))

        missing = _new_settings_without_versionadded(
            baseline_source, current_source
        )
        if missing:
            count = len(missing)
            self.fail(
                "Found %d new %s added to rezconfig that %s missing a "
                "versionadded directive:\n\n%s\n\nNew documented rezconfig "
                "settings must include a preceding "
                "'# .. versionadded:: <version>' directive."
                % (
                    count,
                    "setting" if count == 1 else "settings",
                    "is" if count == 1 else "are",
                    "\n".join("- %s" % name for name in missing),
                )
            )

