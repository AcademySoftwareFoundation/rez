# Change Log

## 2.47.3 (2019-09-28)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.3) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.2...2.47.3)

**Notes**

* GitHub Actions CI test suite added
* Windows not passing currently, fixes to come
* Note that pwsh shell implementation was using the subprocess 'universal_newlines' arg - this has been
  removed. This was causing `execute_shell` to return an str-type stdout/stderr tuple, rather than
  bytes as every other shell impl does, and this was causing tests to fail.

**Merged pull requests:**

- Gh actions - first pass [\#750](https://github.com/nerdvegas/rez/pull/750) ([nerdvegas](https://github.com/nerdvegas))

## 2.47.2 (2019-09-17)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.2) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.1...2.47.2)

**Notes**

Py3 fixes found after testing.

**Merged pull requests:**

- Fix py3 errors and warnings [\#748](https://github.com/nerdvegas/rez/pull/748) ([JeanChristopheMorinPerso](https://github.com/JeanChristopheMorinPerso))


## 2.47.1 (2019-09-17)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.1) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.0...2.47.1)

**Merged pull requests:**

- Issue 696 shell availability [\#747](https://github.com/nerdvegas/rez/pull/747) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- Shell plugin Support API [\#696](https://github.com/nerdvegas/rez/issues/696)


## 2.47.0 (2019-09-13)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.0) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.46.0...2.47.0)

**Notes**

This fixes and improves the shell plugins, especially on Windows for cmd and PowerShell-like.
Formerly excluded shell-dependent tests are now passing.

Note also that this release fixes a regression in Windows, introduced in 2.35.0.

**Merged pull requests:**

- Enhancements for shell plugins [\#698](https://github.com/nerdvegas/rez/pull/698) ([bfloch](https://github.com/bfloch))

**Closed issues:**

- Quotation marks issues on Windows. [\#691](https://github.com/nerdvegas/rez/issues/691)
- Rex and expandable in other shells [\#694](https://github.com/nerdvegas/rez/issues/694)

## 2.46.0 (2019-09-13)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.46.0) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.45.1...2.46.0)

**Notes**

Last round of Py3 updates (not counting further bugfixes found from testing).

Please take note if you notice any changes in performance in Py2. This release includes a number of changes
from methods like `iteritems` to `items`, which in Py2 means a list construction rather than just an iterator.
Tests have shown performance to be identical, but you may find a case where it is not.

**Merged pull requests:**

- py3 iterators conversion [\#736](https://github.com/nerdvegas/rez/pull/736) ([maxnbk](https://github.com/maxnbk))
- py3 finalizations [\#742](https://github.com/nerdvegas/rez/pull/742) ([maxnbk](https://github.com/maxnbk))

## 2.45.1 (2019-09-11)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.45.1) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.45.0...2.45.1)

**Notes**

Misc Py3 compatibility updates, part 4.

**Merged pull requests:**

- robust py2/3 use of getargspec/getfullargspec [\#743](https://github.com/nerdvegas/rez/pull/743) ([nerdvegas](https://github.com/nerdvegas))
- address #744 (rex dictmixin issue) [\#745](https://github.com/nerdvegas/rez/pull/745) ([maxnbk](https://github.com/maxnbk))

**Closed issues:**

- #712 merged in 2.43.0 caused external environ not to pass through to resolve [\#744](https://github.com/nerdvegas/rez/issues/744)


## 2.45.0 (2019-09-10)
[Source](https://github.com/nerdvegas/rez/tree/2.45.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.44.2...2.45.0)

**Notes**

Misc Py3 compatibility updates, part 3.

**Merged pull requests:**

- bytecode / pycache related changes [\#733](https://github.com/nerdvegas/rez/pull/733) ([maxnbk](https://github.com/maxnbk))
- address py3.8 deprecation of collections direct ABC access [\#740](https://github.com/nerdvegas/rez/pull/740) ([maxnbk](https://github.com/maxnbk))
- fix metaclass usage in example code [\#741](https://github.com/nerdvegas/rez/pull/741) ([maxnbk](https://github.com/maxnbk))
- Vendor readme [\#738](https://github.com/nerdvegas/rez/pull/738) ([nerdvegas](https://github.com/nerdvegas))


## 2.44.2 (2019-09-07)
[Source](https://github.com/nerdvegas/rez/tree/2.44.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.44.1...2.44.2)

**Merged pull requests:**

- install variant.json file in the same manner as other extra install files [\#731](https://github.com/nerdvegas/rez/pull/731) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- permissions failure on release (variant.json) [\#730](https://github.com/nerdvegas/rez/issues/730)


## 2.44.1 (2019-09-07)
[Source](https://github.com/nerdvegas/rez/tree/2.44.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.44.0...2.44.1)

**Notes**

Misc Py3 compatibility updates, part 2.

**Merged pull requests:**

- update imports in vendored pydot for py3 [\#728](https://github.com/nerdvegas/rez/pull/728) ([maxnbk](https://github.com/maxnbk))
- update vendored schema for py3 [\#729](https://github.com/nerdvegas/rez/pull/729) ([maxnbk](https://github.com/maxnbk))


## 2.44.0 (2019-09-06)
[Source](https://github.com/nerdvegas/rez/tree/2.44.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.43.0...2.44.0)

**Notes**

Misc Py3 compatibility updates, part 2.

**Merged pull requests:**

- pull basestring from six.string_types - py2 gets basestring, py3 gets str [\#721](https://github.com/nerdvegas/rez/pull/721) ([maxnbk](https://github.com/maxnbk))
- import StringIO from six.moves [\#722](https://github.com/nerdvegas/rez/pull/722) ([maxnbk](https://github.com/maxnbk))
- update vendored colorama from 0.3.1 to 0.4.1 [\#723](https://github.com/nerdvegas/rez/pull/723) ([maxnbk](https://github.com/maxnbk))
- update vendored memcache from 1.5.3 to 1.5.9 [\#724](https://github.com/nerdvegas/rez/pull/724) ([maxnbk](https://github.com/maxnbk))
- make Version properly iterable in py3 [\#725](https://github.com/nerdvegas/rez/pull/725) ([maxnbk](https://github.com/maxnbk))
- modernize function manipulations and attrs [\#727](https://github.com/nerdvegas/rez/pull/727) ([maxnbk](https://github.com/maxnbk))


## 2.43.0 (2019-09-05)
[Source](https://github.com/nerdvegas/rez/tree/2.43.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.42.2...2.43.0)

**Notes**

Misc Py3 compatibility updates.

**Merged pull requests:**

- very small py3 compat changes [\#712](https://github.com/nerdvegas/rez/pull/712) ([maxnbk](https://github.com/maxnbk))
- .next() to next() [\#713](https://github.com/nerdvegas/rez/pull/713) ([maxnbk](https://github.com/maxnbk))
- yaml upgrade [\#714](https://github.com/nerdvegas/rez/pull/714) ([maxnbk](https://github.com/maxnbk))
- improve non-string iterable handling [\#715](https://github.com/nerdvegas/rez/pull/715) ([maxnbk](https://github.com/maxnbk))
- replace async with block to avoid py3 async keyword [\#716](https://github.com/nerdvegas/rez/pull/716) ([maxnbk](https://github.com/maxnbk))
- import queue module through six [\#717](https://github.com/nerdvegas/rez/pull/717) ([maxnbk](https://github.com/maxnbk))
- swap 2.6 support for 3.x in version module [\#718](https://github.com/nerdvegas/rez/pull/718) ([maxnbk](https://github.com/maxnbk))


## 2.42.2 (2019-08-31)
[Source](https://github.com/nerdvegas/rez/tree/2.42.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.42.1...2.42.2)

**Merged pull requests:**

- fixed bez rezbuild.py breaking on old-style print [\#705](https://github.com/nerdvegas/rez/pull/705) ([nerdvegas](https://github.com/nerdvegas))
- zsh tests passing by way of enabling analogue for bash shell completion [\#711](https://github.com/nerdvegas/rez/pull/711) ([maxnbk](https://github.com/maxnbk))


## 2.42.1 (2019-08-31)
[Source](https://github.com/nerdvegas/rez/tree/2.42.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.42.0...2.42.1)

**Notes**

This PR introduces py3 compatibilities that do not functionally alter py2 code.

**Merged pull requests:**

- miscellanous atomic nonaffective py2/py3 compatibilities [\#710](https://github.com/nerdvegas/rez/pull/710) ([maxnbk](https://github.com/maxnbk))


## 2.42.0 (2019-08-30)
[Source](https://github.com/nerdvegas/rez/tree/2.42.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.41.0...2.42.0)

**Merged pull requests:**

- Pip improvements [\#667](https://github.com/nerdvegas/rez/pull/667) ([nerdvegas](https://github.com/nerdvegas))
- remove unneeded backports / vendored libraries [\#702](https://github.com/nerdvegas/rez/pull/702) ([maxnbk](https://github.com/maxnbk))


## 2.41.0 (2019-08-29)
[Source](https://github.com/nerdvegas/rez/tree/2.41.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.40.3...2.41.0)

**Merged pull requests:**

- a few prints to py3-compat [\#701](https://github.com/nerdvegas/rez/pull/701) ([maxnbk](https://github.com/maxnbk))
- Fixing error with changelog referenced before assigment [\#700](https://github.com/nerdvegas/rez/pull/700) ([bareya](https://github.com/bareya))
- Adding GCC bind [\#699](https://github.com/nerdvegas/rez/pull/699) ([bareya](https://github.com/bareya))


## 2.40.3 (2019-08-15)
[Source](https://github.com/nerdvegas/rez/tree/2.40.3) | [Diff](https://github.com/nerdvegas/rez/compare/2.40.2...2.40.3)

**Notes**

This update allows custom plugins to override the builtin rez plugins. It does so by reversing the order
in which plugins are loaded, so that builtins are loaded last.

**Merged pull requests:**

- Reverse order for plugins loading [\#692](https://github.com/nerdvegas/rez/pull/692) ([predat](https://github.com/predat))

**Closed issues:**

- rezplugins loading order [\#677](https://github.com/nerdvegas/rez/issues/677)


## 2.40.2 (2019-08-15)
[Source](https://github.com/nerdvegas/rez/tree/2.40.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.40.1...2.40.2)

**Notes**

This release fixes an issue on Windows, which has non-case-sensitive filepaths. Requesting a package with a case
differing from that on disk would cause two packages to exist in the resolve, which really were just different
cases of the same package.

The behaviour on Windows is now:

- Packages are case-sensitive - `rez-env Foo` will fail if the package folder on disk is `foo`;
- Package repository paths are case-insensitive - `~/packages` and `~/Packages` are regarded as the same repo.

**Merged pull requests:**

- [FIX] Make package resolve request respect case sensitivity -- Windows [\#689](https://github.com/nerdvegas/rez/pull/689) ([lambdaclan](https://github.com/lambdaclan))


## 2.40.1 (2019-08-07)
[Source](https://github.com/nerdvegas/rez/tree/2.40.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.40.0...2.40.1)

**Notes**

Fixes regression introduced in v2.39.0.

**Merged pull requests:**

- added missing plugin config [\#690](https://github.com/nerdvegas/rez/pull/690) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- [Regression - Version >= 2.39.0] ConfigurationError: Error in Rez configuration under plugins.shell [\#688](https://github.com/nerdvegas/rez/issues/688)


## 2.40.0 (2019-08-07)
[Source](https://github.com/nerdvegas/rez/tree/2.40.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.39.0...2.40.0)

**Notes**

- Adds new Zsh shell plugin (**BETA**)

**Merged pull requests:**

- initial implementation of zsh shell plugin [\#686](https://github.com/nerdvegas/rez/pull/686) ([maxnbk](https://github.com/maxnbk))

**Closed issues:**

- zsh plugin for rez [\#451](https://github.com/nerdvegas/rez/issues/451)


## 2.39.0 (2019-08-07)
[Source](https://github.com/nerdvegas/rez/tree/2.39.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.38.2...2.39.0)

**Notes**

- Fixes errors in new powershell plugin
- Adds new powershell core 6+ plugin (**BETA**).

**Merged pull requests:**

- Fix missing import in powershell plugin [\#674](https://github.com/nerdvegas/rez/pull/674) ([instinct-vfx](https://github.com/instinct-vfx))
- Add powershell core 6+ support (pwsh) [\#679](https://github.com/nerdvegas/rez/pull/679) ([instinct-vfx](https://github.com/instinct-vfx))

**Closed issues:**

- Add shell plugin for poweshell 6+ [\#678](https://github.com/nerdvegas/rez/issues/678)


## 2.38.2 (2019-07-23)
[Source](https://github.com/nerdvegas/rez/tree/2.38.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.38.1...2.38.2)

**Notes**

Fixes regression in 2.38.0 that unintentionally renamed _rez_fwd tool to _rez-fwd.

**Merged pull requests:**

- fixed regression in 2.38.0 that unintentionally renamed _rez_fwd to _rez-fwd [\#676](https://github.com/nerdvegas/rez/pull/676) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- build scripts generated with incorrect shebang arg [\#671](https://github.com/nerdvegas/rez/issues/671)


## 2.38.1 (2019-07-20)
[Source](https://github.com/nerdvegas/rez/tree/2.38.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.38.0...2.38.1)

**Notes**

Fixes issue on Windows where rez-bind'ing pip creates a broken package.

**Merged pull requests:**

- [Fix] Windows rez-bind pip [\#659](https://github.com/nerdvegas/rez/pull/659) ([lambdaclan](https://github.com/lambdaclan))


## 2.38.0 (2019-07-20)
[Source](https://github.com/nerdvegas/rez/tree/2.38.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.37.1...2.38.0)

**Notes**

Updates the installer (install.py).

* patched distlib (in build_utils) has been removed. The patch we were relying on
  has since been made part of the main distlib release, which we already have vendored;
* virtualenv has been updated to latest;
* scripts have been removed, and entry points are used instead;
* install.py code has been cleaned up and simplified. Specifically, standard use of
  distlib.ScriptMaker has been put in place;
* INSTALL.md has been updated with a full explanation of the installer, and why a
  pip-based installation is not the same as using install.py.

**Merged pull requests:**

- Installer updates [\#662](https://github.com/nerdvegas/rez/pull/662) ([nerdvegas](https://github.com/nerdvegas))


## [2.37.1](https://github.com/nerdvegas/rez/tree/2.37.1) (2019-07-20)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.37.0...2.37.1)

**Notes**

This fixes a regression introduced in `2.34.0`, which causes `rez-context -g` to
fail. The pydot vendor package was updated, and the newer version includes a
breaking change. Where `pydot.graph_from_dot_data` used to return a single graph
object, it now returns a list of graph objects.

**Merged pull requests:**

- Fix pydot regression [\#668](https://github.com/nerdvegas/rez/pull/668) ([nerdvegas](https://github.com/nerdvegas))


## [2.37.0](https://github.com/nerdvegas/rez/tree/2.37.0) (2019-07-19)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.36.2...2.37.0)

**Notes**

Adds PowerShell support.
https://docs.microsoft.com/en-us/powershell/

**Merged pull requests:**

- Implement PowerShell [\#644](https://github.com/nerdvegas/rez/pull/644) ([mottosso](https://github.com/mottosso))


## [2.36.2](https://github.com/nerdvegas/rez/tree/2.36.2) (2019-07-16)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.36.1...2.36.2)

**Merged pull requests:**

- [Feature] Pure python package detection [\#628](https://github.com/nerdvegas/rez/pull/628) ([lambdaclan](https://github.com/lambdaclan))


## [2.36.1](https://github.com/nerdvegas/rez/tree/2.36.1) (2019-07-16)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.36.0...2.36.1)

**Merged pull requests:**

- [Fix] Sh failing in `test_shells.TeshShells.text_rex_code_alias` [\#663](https://github.com/nerdvegas/rez/pull/663) ([bfloch](https://github.com/bfloch))


## [2.36.0](https://github.com/nerdvegas/rez/tree/2.36.0) (2019-07-16)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.35.0...2.36.0)

**Merged pull requests:**

- Add a package_preprocess_mode [\#651](https://github.com/nerdvegas/rez/pull/651) ([JeanChristopheMorinPerso](https://github.com/JeanChristopheMorinPerso))

**Closed issues:**

- Support "additive" preprocess functions [\#609](https://github.com/nerdvegas/rez/issues/609)


## [2.35.0](https://github.com/nerdvegas/rez/tree/2.35.0) (2019-07-10)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.34.0...2.35.0)

**Backwards Compatibility Issues**

Please note that this update alters the process hierarchy of a resolved rez environment,
for Windows users. This does not necessarily represent a compatibility issue, but please
be on the lookout for unintended side effects and report them if they arise.

**Merged pull requests:**

- WIP No more "Terminate Batch Job? (Y/N)" - Take 2 [\#627](https://github.com/nerdvegas/rez/pull/627) ([mottosso](https://github.com/mottosso))

**Closed issues:**

- Shell history not working in cmd.exe or PowerShell [\#616](https://github.com/nerdvegas/rez/issues/616)


## [2.34.0](https://github.com/nerdvegas/rez/tree/2.34.0) (2019-07-10)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.33.0...2.34.0)

**Merged pull requests:**

- [Fix] Wheel pip regressions [\#656](https://github.com/nerdvegas/rez/pull/656) ([lambdaclan](https://github.com/lambdaclan))


## [2.33.0](https://github.com/nerdvegas/rez/tree/2.33.0) (2019-06-26)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.32.1...2.33.0)

**Merged pull requests:**

- Update distlib vendor library [\#654](https://github.com/nerdvegas/rez/pull/654) ([lambdaclan](https://github.com/lambdaclan))
- [WIP] Feature/pip install modern [\#602](https://github.com/nerdvegas/rez/pull/602) ([lambdaclan](https://github.com/lambdaclan))


## [2.32.1](https://github.com/nerdvegas/rez/tree/2.32.1) (2019-06-24)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.32.0...2.32.1)

**Merged pull requests:**

- Support for external PyYAML and Python 3 [\#622](https://github.com/nerdvegas/rez/pull/622) ([mottosso](https://github.com/mottosso))
- Fix escaping backslashes in tcsh on Mac OS [\#497](https://github.com/nerdvegas/rez/pull/497) ([skral](https://github.com/skral))


## [2.32.0](https://github.com/nerdvegas/rez/tree/2.32.0) (2019-06-23)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.31.4...2.32.0)

**Merged pull requests:**

- Implement preprocess function support for rezconfig.py (takeover) [\#650](https://github.com/nerdvegas/rez/pull/650) ([JeanChristopheMorinPerso](https://github.com/JeanChristopheMorinPerso))


## [2.31.4](https://github.com/nerdvegas/rez/tree/2.31.4) (2019-06-22)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.31.3...2.31.4)

**Merged pull requests:**

- Expose Python standard module __file__ and __name__ to rezconfig [\#636](https://github.com/nerdvegas/rez/pull/636) ([mottosso](https://github.com/mottosso))


## [2.31.3](https://github.com/nerdvegas/rez/tree/2.31.3) (2019-06-22)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.31.2...2.31.3)

**Merged pull requests:**

- Bugfix for alias() on Windows [\#607](https://github.com/nerdvegas/rez/pull/607) ([mottosso](https://github.com/mottosso))


## [2.31.2](https://github.com/nerdvegas/rez/tree/2.31.2) (2019-06-22)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.31.1...2.31.2)

**Merged pull requests:**

- Fix #558 [\#647](https://github.com/nerdvegas/rez/pull/647) ([mottosso](https://github.com/mottosso))

**Closed issues:**

- rez-build breaks if "|" in a required package's version on Windows [\#558](https://github.com/nerdvegas/rez/issues/558)


## [2.31.1](https://github.com/nerdvegas/rez/tree/2.31.1) (2019-06-18)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.31.0...2.31.1)

**Merged pull requests:**

- Automatically create missing package repository dir [\#623](https://github.com/nerdvegas/rez/pull/623) ([mottosso](https://github.com/mottosso))


## [2.31.0](https://github.com/nerdvegas/rez/tree/2.31.0) (2019-06-04)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.30.2...2.31.0)

**Merged pull requests:**

- Fix/add support for reversed version range [\#618](https://github.com/nerdvegas/rez/pull/618) ([instinct-vfx](https://github.com/instinct-vfx))


## [2.30.2](https://github.com/nerdvegas/rez/tree/2.30.2) (2019-06-03)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.30.1...2.30.2)

**Merged pull requests:**

- Update print statements to be Python 3 compatible [\#641](https://github.com/nerdvegas/rez/pull/641) ([bpabel](https://github.com/bpabel))


## [2.30.1](https://github.com/nerdvegas/rez/tree/2.30.1) (2019-06-03)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.30.0...2.30.1)

**Merged pull requests:**

- WIP Fix file permissions of package.py on Windows [\#598](https://github.com/nerdvegas/rez/pull/598) ([mottosso](https://github.com/mottosso))


## [2.30.0](https://github.com/nerdvegas/rez/tree/2.30.0) (2019-05-07)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.29.1...2.30.0)

**Merged pull requests:**

- fqdn [\#621](https://github.com/nerdvegas/rez/pull/621) ([bpabel](https://github.com/bpabel))
- Fix path list with whitespace [\#588](https://github.com/nerdvegas/rez/pull/588) ([asztalosdani](https://github.com/asztalosdani))
- Close the amqp connection after message publish [\#615](https://github.com/nerdvegas/rez/pull/615) ([loup-kreidl](https://github.com/loup-kreidl))

**Closed issues:**

- rezbuild.py broken [\#619](https://github.com/nerdvegas/rez/issues/619)
- rez-env Performance and socket.getfqdn() [\#617](https://github.com/nerdvegas/rez/issues/617)
- "parse_build_args.py" file parser arguments are not accessible anymore in "os.environ". [\#590](https://github.com/nerdvegas/rez/issues/590)


## [2.29.1](https://github.com/nerdvegas/rez/tree/2.29.1) (2019-04-22)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.29.0...2.29.1)

**Merged pull requests:**

- Bugfix/custom build arguments [\#601](https://github.com/nerdvegas/rez/pull/601) ([lambdaclan](https://github.com/lambdaclan))

**Closed issues:**

- bug in rez-build --bs option [\#604](https://github.com/nerdvegas/rez/issues/604)


## [2.29.0](https://github.com/nerdvegas/rez/tree/2.29.0) (2019-04-09)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.28.0...2.29.0)

**Implemented enhancements:**

- hash-based variant subpaths [\#583](https://github.com/nerdvegas/rez/issues/583)

**Closed issues:**

- rez variant environment var during build [\#304](https://github.com/nerdvegas/rez/issues/304)


## [2.28.0](https://github.com/nerdvegas/rez/tree/2.28.0) (2019-03-15)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.27.1...2.28.0)

**Fixed bugs:**

- nargs errors for logging_.print_* functions [\#580](https://github.com/nerdvegas/rez/issues/580)

**Merged pull requests:**

- Ignore versions if .ignore file exists [\#453](https://github.com/nerdvegas/rez/pull/453) ([Pixomondo](https://github.com/Pixomondo))
- Fix/logging print nargs [\#581](https://github.com/nerdvegas/rez/pull/581) ([wwfxuk](https://github.com/wwfxuk))
- package_test.py: fix rez-test header command with % [\#572](https://github.com/nerdvegas/rez/pull/572) ([rodeofx](https://github.com/rodeofx))
- Call the flush method every time a Printer instance is called [\#540](https://github.com/nerdvegas/rez/pull/540) ([rodeofx](https://github.com/rodeofx))


## [2.27.1](https://github.com/nerdvegas/rez/tree/2.27.1) (2019-03-15)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.27.0...2.27.1)

**Merged pull requests:**

- Delete old repository directory [\#576](https://github.com/nerdvegas/rez/pull/576) ([bpabel](https://github.com/bpabel))


## [2.27.0](https://github.com/nerdvegas/rez/tree/2.27.0) (2019-01-24)
[Full Changelog](https://github.com/nerdvegas/rez/compare/2.26.4...2.27.0)

**Implemented enhancements:**

- facilitate variant install when target package is read-only [\#565](https://github.com/nerdvegas/rez/issues/565)

**Fixed bugs:**

- timestamp override no working in package copy [\#568](https://github.com/nerdvegas/rez/issues/568)
- shallow rez-cp can corrupt package if there are overlapping variants [\#563](https://github.com/nerdvegas/rez/issues/563)

**Merged pull requests:**

- Issue 568 [\#569](https://github.com/nerdvegas/rez/pull/569) ([nerdvegas](https://github.com/nerdvegas))
- Issue 565 [\#567](https://github.com/nerdvegas/rez/pull/567) ([nerdvegas](https://github.com/nerdvegas))
- Issue 563 [\#566](https://github.com/nerdvegas/rez/pull/566) ([nerdvegas](https://github.com/nerdvegas))


## 2.26.4 [[#562](https://github.com/nerdvegas/rez/pull/562)] Fixed Regression in 2.24.0

#### Addressed Issues

* [#561](https://github.com/nerdvegas/rez/issues/561) timestamp not written to installed package


## 2.26.3 [[#560](https://github.com/nerdvegas/rez/pull/560)] Package.py permissions issue

#### Addressed Issues

* [#559](https://github.com/nerdvegas/rez/issues/559) package.py permissions issue

#### Notes

Fixes issue where installed `package.py` can be set to r/w for only the current user.


## 2.26.2 [[#557](https://github.com/nerdvegas/rez/pull/557)] Package Copy Fixes For Non-Varianted Packages

#### Addressed Issues

* [#556](https://github.com/nerdvegas/rez/issues/556) rez-cp briefly copies original package definition in non-varianted packages
* [#555](https://github.com/nerdvegas/rez/issues/555) rez-cp inconsistent symlinking when --shallow=true
* [#554](https://github.com/nerdvegas/rez/issues/554) rez-cp doesn't keep file metadata in some cases

#### Notes

There were various minor issues related to copying non-varianted packages.


## 2.26.1 [[#552](https://github.com/nerdvegas/rez/pull/552)] Bugfix in Package Copy

#### Addressed Issues

* [#551](https://github.com/nerdvegas/rez/issues/551) package copy fails if symlinks in root dir

#### Notes

This was failing when symlinks were present within a non-varianted package being copied. Now, these
symlinks are retained in the target package, unless `--follow-symlinks` is specified.


## 2.26.0 [[#550](https://github.com/nerdvegas/rez/pull/550)] Build System Detection Fixes

#### Addressed Issues

* [#549](https://github.com/nerdvegas/rez/issues/549) '--build-system' rez-build option not always
  available

#### Notes

To fix this issue:
* The '--build-system' rez-build option is now always present.
* To provide further control over the build system type, the package itself can now specify its build
  system - see https://github.com/nerdvegas/rez/wiki/Package-Definition-Guide#build_system

#### COMPATIBILITY ISSUE!

Unfortunately, the 'cmake' build system had its own '--build-system' commandline option also. This
was possible because previous rez versions suppressed the standard '--build-system' option if only
one valid build system was present for a given package working directory. **This option has been
changed to '--cmake-build-system'**.


## 2.25.0 [[#548](https://github.com/nerdvegas/rez/pull/548)] Various Build-related issues

#### Addressed Issues

* [#433](https://github.com/nerdvegas/rez/issues/433): "package_definition_build_python_paths" defined
  paths are not available from top level in package.py
* [#442](https://github.com/nerdvegas/rez/issues/442): "rez-depends" and "private_build_requires"
* [#416](https://github.com/nerdvegas/rez/issues/416): Need currently-building-variant build variables
* [#547](https://github.com/nerdvegas/rez/issues/547): rez-cp follows symlinks within package payload

#### Notes

The biggest update in this release is the introduction of new variables accessible at early-bind time:
building, build_variant_index and build_variant_requires. This allows you to do things like define
different private_build_requires per-variant, or a requires that is different at runtime than it is
at build time. In order to get this to work, a package.py is now re-evaluated multiple times when a
build occurs - once pre-build (where 'building' is set to False), and once per variant build. Please
see the updated wiki for more details: https://github.com/nerdvegas/rez/wiki/Package-Definition-Guide#available-objects

A new build-time env-var, REZ_BUILD_VARIANT_REQUIRES, has been added. This mirrors the new
build_variant_requires var mentioned above.

rez-depends has been updated to only include the private_build_requires of the package being queried
(previously, all packages' private build reqs were included, which is not useful). Recall that the
previous release fixes the issue where private_build_requires was being stripped from released
packages.

The entirety of a package definition file can now see the extra build-time modules available via the
package_definition_build_python_paths config setting. Previously, only early bound functions could
see these.

There was an issue with package copying (and thus the rez-cp tool) where symlinks within a package's
payload were expanded out to their source files at copy time. The default now is to keep such symlinks
intact - but hte previous behavior can still be accessed with the rez-cp --follow-symlinks option.


## 2.24.0: Package Copying

This release adds a new tool, rez-cp, for copying packages/variants from one package repository to
another, with optional renaming/reversioning. The associated API can be found in src/package_copy.py.

#### Addressed Issues

* #541
* #510
* #477

#### Notes

* Package definition file writes are now atomic;
* private_build_requires is kept in installed/released packages;
* Fixes include modules not being copied into released packages;
* File lock is no longer created when variant installation happens in dry mode.


## 2.23.1: Fixed Regression in 2.20.0

#### Addressed Issues

* #532

#### Notes

Bug was introduced in: https://github.com/nerdvegas/rez/releases/tag/2.20.0


## 2.23.0: Package Usage Tracking, Better Config Overrides

#### Addressed Issues

* #528

#### Notes

Two new features are added in this release:

Override any config setting with an env-var. For any setting "foo", you can now set the env-var
REZ_FOO_JSON to a JSON-encoded string. This works for any config setting. Note that the existing
REZ_FOO env-var overrides are still in place also; if both are defined, REZ_FOO takes precedence.
This feature means you can now override some of the more complicated settings with env-vars, such as
package_filter.

Track context creation and sourcing via AMQP. Messages are published (on a separate thread) to the
nominated broker/exchange/routing_key. You have control over what parts of the context are published.
For more details: https://github.com/nerdvegas/rez/blob/master/src/rez/rezconfig.py#L414

The embedded simplejson lib was removed. The native json lib is used instead, and for cases where loads-without-unicoding-everything is needed, utils/json.py now addresses that instead.


## 2.22.1: Stdin-related fixes

#### Addressed Issues

* #512
* #526


## 2.22.0: Search API

PR: #213

#### Notes

Package/variant/family search API is now available in package_search.py. This gives the same
functionality as provided by the rez-search CLI tool.


## 2.21.0: Added mingw as a rez build_system for cmake

PR: #501


## 2.20.1: Windows Fixes

#### Merged PRs

* #490: Fix alias command in Windows when PATH is modified
* #489: Fix cmd.exe not escaping special characters
* #482: Fix selftest getting stuck on Windows

#### Addressed Issues

* #389
* #343
* #432
* #481


## 2.20.0: Better CLI Arg Parsing

PR: #523

#### Addressed Issues

* #492

#### Notes

The rez-python command now supports all native python args and passes those through to its python
subprocess - so you can now shebang with rez-python if that is useful.

More broadly, rez commands now parse CLI args correctly for each case. Many commands previously
accepted rez-env-style commands (eg rez-env pkgA -- somecommand -- i am ignored), but simply ignored
extraneous args after -- tokens.


## 2.19.1: Fixed bug with rez-build and package preprocess

#### Merged PRs

* #522

#### Addressed Issues

* #514

#### Notes

The problem occurred because the preprocess function was attempting to be serialized when the package
definition is cached to memcache. However, this function is stripped in installed packages;
furthermore, caching "developer packages" (ie unbuilt packages) was never intentional.

This release disables memcaching of developer packages, thus avoiding the bug and bringing back
originally intended behavior.
