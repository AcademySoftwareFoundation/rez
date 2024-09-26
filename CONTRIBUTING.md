# Contributing To Rez

Thank you for your interest in contributing to rez.
This document explains our contribution process and procedures, so please review it first:

* [Get Connected](#Get-Connected)
* [Guidelines](#Guidelines)
* [Development Environment](#Development-Environment)
* [Legal Requirements](#Legal-Requirements)
* [Reporting Bugs](#Reporting-Bugs)
* [Versioning Policy](#Versioning-Policy)

For a description of the roles and responsibilities of the various members of the rez community, see [GOVERNANCE](GOVERNANCE.md), and
for further details, see the project's
[Technical Charter](https://github.com/AcademySoftwareFoundation/foundation/blob/main/project_charters/rez-charter.pdf). Briefly, Contributors are anyone
who submits content to the project, Committers review and approve such
submissions, and the Technical Steering Committee provides general project
oversight and maintainership.

## Get Connected

The first thing to do, before anything else, is talk to us! Whether you're
reporting an issue, requesting or implementing a feature, or just asking a
question; please don’t hesitate to reach out to project maintainers or the
community as a whole. This is an important first step because your issue,
feature, or the question may have been solved or discussed already, and you’ll
save yourself a lot of time by asking first.

How do you talk to us? There are several ways to get in touch:

* [Slack](https://slack.aswf.io):
Join the ``#rez`` channel. This channel is where the majority of rez-centric
discussion takes place, where announcements are made, where users help each
other, and other relevant community information is released.

There are a number of other helpful channels as well, depending on your
tolerance for high-frequency information, such as:
``#rez-gh-releases``, ``#rez-gh-prs``, and ``#rez-gh-issues``.

* [GitHub Discussions](https://github.com/AcademySoftwareFoundation/rez/discussions):
GitHub **discussions** are a great place to start a conversation! It's an
excellent place to ask both the rez maintainers as well as the general community
any questions, as well as to act as a place to facilitate complex topics such as
those related to development, rez future feature-set, or future goals of the
project!

* [rez-discussion mailing list](https://lists.aswf.io/g/rez-discussion/):
This is a general-purpose mailing list for discussion of rez, its features,
behavior, configuration, usage patterns, and sometimes a channel for information
regarding major releases. Put simply, a slower version of our Slack channel.

* [The monthly TSC meeting](https://www.aswf.io/meeting-calendar/):
Check the calendar for our monthly TSC meeting. Reminders often posted in Slack.

## Guidelines

If you would like to contribute code you can do so through GitHub by forking the
repository and sending a pull request. Please follow these guidelines:

1.  Always retain backwards compatibility, unless a breaking change is necessary. If it is
    necessary, the associated release notes must make this explicit and obvious;
2.  Make every effort to follow existing conventions and style;
3.  Follow [PEP8](https://www.python.org/dev/peps/pep-0008/);
4.  Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
    for docstrings;
5.  Use *spaces*, not *tabs*;
6.  Update the [rez version](src/rez/utils/_version.py) appropriately, and follow
    [semantic versioning](https://semver.org/);
7.  Use [this format](https://help.github.com/articles/closing-issues-using-keywords/)
    to mention the issue(s) your PR closes;
8.  Add relevant tests to demonstrate that your changes work;
9.  Add relevant documentation [here](docs/source) to document your changes, if applicable. Those
    markdown files prefixed with `_` are internal and should not be changed.
10. If your changes add a new rez config setting, update [rezconfig.py](src/rez/rezconfig.py) and
    document the setting. The comments in this file are extracted and turned into documentation. Pay
    attention to the comment formatting and follow the existing style closely.

## Development Environment

### Prerequisites 

On Windows, make sure to set your PowerShell execution policy as shown [here](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-executionpolicy?view=powershell-5.1),
otherwise the PowerShell tests will fail.

### Setting Up

To begin development on rez you'll first need to set up your development environment. There are many 
ways you can do it, but these are the recommended approaches.

This first approach will automatically create a virtual environment for you, patch the Rez binaries, 
and copy completion scripts. All tests will be run this way.

1. Fork the repo and clone it.
2. Create a new Git branch and check it out.
3. Install your local rez code by running `python install.py venv`.
4. Activate the virtual environment by running the `activate` file.
5. Add the `Scripts/rez` folder on Windows or the `bin/rez` folder on Mac/Linux to the `PATH` environment variable.

There is an alternative method of setting up your development environment, that doesn't use the `install.py`
script. Please note that not all tests will be run if rez is installed this way.

1. Fork the repo and clone it.
2. Create a new Git branch and check it out.
3. Create a virtual environment in the same directory as the repo by running `python -m venv venv`.
4. Activate the virtual environment by running the `activate` file.
5. Pip install your local rez code by running `pip install .`.

Additionally, if you are going to run tests in the repo, you may want to install two additional optional 
packages for improved test output: `pytest` and `parameterized`. You can install these by running 
`pip install pytest parameterized`.

### Running Tests

1. Set up your development environment as shown above.
2. Run `rez selftest`.

## Legal Requirements

rez is a project hosted by the Academy Software Foundation (ASWF) and
follows the open source software best practice policies of the ASWF TAC with the
guidance from the Linux Foundation.

### License

rez is licensed under the [Apache 2.0 License](LICENSE). Contributions to rez
should abide by that license.

### Contributor License Agreements

Developers who wish to contribute code to be considered for inclusion
in rez must first complete a **Contributor License Agreement
(CLA)**.

rez uses [EasyCLA](https://lfx.linuxfoundation.org/tools/easycla) for managing CLAs, which
automatically checks to ensure CLAs are signed by a contributor before a commit
can be merged.

* If you are an individual writing the code on your own time and
  you're SURE you are the sole owner of any intellectual property you
  contribute, you can
  [sign the CLA as an individual contributor](https://docs.linuxfoundation.org/lfx/easycla/contributors/individual-contributor).

* If you are writing the code as part of your job, or if there is any
  possibility that your employers might think they own any
  intellectual property you create, then you should use the 
  [Corporate Contributor Licence Agreement](https://docs.linuxfoundation.org/lfx/easycla/contributors/corporate-contributor).

The rez CLA's are the standard forms used by Linux Foundation projects and
[recommended by the ASWF TAC](https://github.com/AcademySoftwareFoundation/tac/blob/main/process/contributing.md#contributor-license-agreement-cla).

### DCO Commit Sign-Off

Rez enforces Developer Certificate of Origin (DCO) on all commits, as per ASWF guidelines. PRs are automatically blocked until all commits within the PR are signed off.

To automatically add the necessary sign-off line to every commit, we suggest you do the following,
in the root of the project (you'll only need to do it once, and the template file has been added
to `.gitignore`):

```
]$ echo "Signed-off-by: $(git config user.name) <$(git config user.email)>" > .git-commit-template
]$ git config commit.template .git-commit-template
```

For more info see https://github.blog/changelog/2022-06-08-admins-can-require-sign-off-on-web-based-commits/
for web-based commits, and https://probot.github.io/apps/dco/ for all others.

### Copyright Notices

All new source files should begin with a copyright and license stating:

```
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project
```

## Reporting Bugs

If you report a bug, please ensure to specify the following:

1.  Rez version (e.g. 2.18.0);
2.  Platform and operating system you were using;
3.  Contextual information (what were you trying to do using Rez);
4.  Simplest possible steps to reproduce.

## Versioning Policy

rez releases observe the [semver 2.0.0](https://semver.org/) version numbering standard.
Briefly:

* **MAJOR** version when you make incompatible API changes
* **MINOR** version when you add functionality in a backward compatible manner
* **PATCH** version when you make backward compatible bug fixes
