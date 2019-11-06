# Contributing To Rez

If you would like to contribute code you can do so through GitHub by forking the repository and
sending a pull request. Please follow these guidelines:

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
9.  Add relevant documentation [here](wiki/pages) to document your changes, if applicable. Those
    markdown files prefixed with `_` are internal and should not be changed.
10. If you changes add a new rez config setting, update [rezconfig.py](src/rez/rezconfig.py) and
    document the setting. The comments in this file are extracted and turned into Wiki content. Pay
    attention to the comment formatting and follow the existing style closely.

## Windows Docker Workflow

The Windows tests currently build a Python image for each version to test. Each is based on a common
base image. Any changes to the following Docker images sources should be a separate commit:

- `.github/docker/rez-win-base/**`
- `.github/docker/rez-win-py/**`
- `.github/workflows/windows-docker-image.yaml`

The base and Python images will be automatically rebuild.
Any future commits will pickup the correct image via `windows-docker.yaml`

## Reporting Bugs

If you report a bug, please ensure to specify the following:

1.  Rez version (e.g. 2.18.0);
2.  Platform and operating system you were using;
3.  Contextual information (what were you trying to do using Rez);
4.  Simplest possible steps to reproduce.
