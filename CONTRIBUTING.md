# Contributing To Rez

If you would like to contribute code you can do so through GitHub by forking the repository and
sending a pull request. Please follow these guidelines:

1.  Always retain backwards compatibility, unless a breaking change is necessary. If it is necessary, the associated
    release notes must make this explicit and obvious;
2.  Make every effort to follow existing conventions and style;
3.  Follow [PEP8](https://www.python.org/dev/peps/pep-0008/);
4.  Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
    for docstrings;
5.  Use *spaces*, not *tabs*;
6.  Update the [rez version](https://github.com/nerdvegas/rez/blob/master/src/rez/utils/_version.py) appropriately, and
    follow [semantic versioning](https://semver.org/);
7.  Update [the changelog](https://github.com/nerdvegas/rez/blob/master/CHANGELOG.md); see the section below for more
    details;
8.  Use [this format](https://help.github.com/articles/closing-issues-using-keywords/) to mention the issue(s) your PR
    closes;
9.  Add relevant tests to demonstrate that your changes work;
10. Add relevant documentation (see [here](https://github.com/nerdvegas/rez/blob/master/wiki/README.md)) to document your
    changes, if applicable.

## Reporting Bugs

If you report a bug, please ensure to specify the following:

1.  Rez version (e.g. 2.18.0);
2.  Platform and operating system you were using;
3.  Contextual information (what were you trying to do using Rez);
4.  Simplest possible steps to reproduce.

## Updating The Changelog

Here is an example changelog entry:

```
## [2.30.0](https://github.com/nerdvegas/rez/tree/2.30.0) (2019-05-07)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.29.1...2.30.0)

**Notes**

Describe the fixes the PR addresses here. It's ok if this is a summary of a longer
description found in the PR itself, in fact that should be common.

**Backwards Compatibility Issues**

Describe any backwards compatiblity issues here. If there are none, do not include
this section. Any breaking changes should be rare and only introduced for good
reason.

**Merged pull requests:**

- PR_TITLE_HERE [\#XXX](https://github.com/nerdvegas/rez/pull/XXX) ([USER](https://github.com/USER))

**Closed issues:**

- ISSUE_TITLE_HERE [\#YYY](https://github.com/nerdvegas/rez/issues/YYY)
```

Please include the relevant issues that your PR closes, matching the syntax shown above. When the PR is merged to master, the PR info will be added to the same changelog entry by the maintainer. Don't be too concerned with the date and 'full changelog' line, this will also be patched by the maintainer.
