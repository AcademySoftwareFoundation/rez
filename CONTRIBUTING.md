# Contributing To Rez

## Guidelines

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

## CLA

Rez enforces use of a Contributor License Agreement as per ASWF guidelines. You need only sign up to the EasyCLA system once, but until you do, your PRs will be automatically blocked.

For more info see https://easycla.lfx.linuxfoundation.org/#/

## DCO

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

## Reporting Bugs

If you report a bug, please ensure to specify the following:

1.  Rez version (e.g. 2.18.0);
2.  Platform and operating system you were using;
3.  Contextual information (what were you trying to do using Rez);
4.  Simplest possible steps to reproduce.
