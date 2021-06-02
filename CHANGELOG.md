# Change Log

## 2.89.1 (2021-06-02)
[Source](https://github.com/nerdvegas/rez/tree/2.89.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.89.0...2.89.1)

**Merged pull requests:**

- disable memcache when ignoring hidden pkgs [\#1090](https://github.com/nerdvegas/rez/pull/1090) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- rez-rm --ignored-since faulty in combo with memcached enabled [\#1089](https://github.com/nerdvegas/rez/issues/1089)

## 2.89.0 (2021-06-01)
[Source](https://github.com/nerdvegas/rez/tree/2.89.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.88.4...2.89.0)

**Merged pull requests:**

- Improve context resolve failure info [\#1083](https://github.com/nerdvegas/rez/pull/1083) ([davidlatwe](https://github.com/davidlatwe))

## 2.88.4 (2021-06-01)
[Source](https://github.com/nerdvegas/rez/tree/2.88.4) | [Diff](https://github.com/nerdvegas/rez/compare/2.88.3...2.88.4)

**Merged pull requests:**

- Fix conflict fail graph #865 [\#1087](https://github.com/nerdvegas/rez/pull/1087) ([davidlatwe](https://github.com/davidlatwe))

**Closed issues:**

- fail-graph not showing true root of the conflict [\#865](https://github.com/nerdvegas/rez/issues/865)

## 2.88.3 (2021-06-01)
[Source](https://github.com/nerdvegas/rez/tree/2.88.3) | [Diff](https://github.com/nerdvegas/rez/compare/2.88.2...2.88.3)

**Merged pull requests:**

- Refactor: Split add_standard_build_actions introducing add_pre_build_commands [\#1077](https://github.com/nerdvegas/rez/pull/1077) ([Tilix4](https://github.com/Tilix4))

**Closed issues:**

- include could not find load file: RezBuild error on Windows [\#974](https://github.com/nerdvegas/rez/issues/974)

## 2.88.2 (2021-05-20)
[Source](https://github.com/nerdvegas/rez/tree/2.88.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.88.1...2.88.2)

**Merged pull requests:**

- added rez_version to context tracking amqp message [\#1079](https://github.com/nerdvegas/rez/pull/1079) ([nerdvegas](https://github.com/nerdvegas))

## 2.88.1 (2021-05-18)
[Source](https://github.com/nerdvegas/rez/tree/2.88.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.88.0...2.88.1)

**Merged pull requests:**

- switch to cached root in variant binding [\#1076](https://github.com/nerdvegas/rez/pull/1076) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- windows package cache root switch does only work with "{root}" not this.root  [\#1065](https://github.com/nerdvegas/rez/issues/1065)

## 2.88.0 (2021-05-13)
[Source](https://github.com/nerdvegas/rez/tree/2.88.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.87.0...2.88.0)

**Notes**

This is currently implemented for linux only.

**Closed issues:**

- fix linking within bundles [\#1072](https://github.com/nerdvegas/rez/issues/1072)

## 2.87.0 (2021-05-11)
[Source](https://github.com/nerdvegas/rez/tree/2.87.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.86.1...2.87.0)

**Merged pull requests:**

- added bundle support for a post_commands.py file [\#1073](https://github.com/nerdvegas/rez/pull/1073) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- add post-context rex file in bundles [\#1071](https://github.com/nerdvegas/rez/issues/1071)

## 2.86.1 (2021-05-04)
[Source](https://github.com/nerdvegas/rez/tree/2.86.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.86.0...2.86.1)

**Merged pull requests:**

- Fix pkg cache test [\#1046](https://github.com/nerdvegas/rez/pull/1046) ([davidlatwe](https://github.com/davidlatwe))

## 2.86.0 (2021-05-04)
[Source](https://github.com/nerdvegas/rez/tree/2.86.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.85.0...2.86.0)

**Merged pull requests:**

- rez config --json FIELD [\#1064](https://github.com/nerdvegas/rez/pull/1064) ([j0yu](https://github.com/j0yu))

## 2.85.0 (2021-05-04)
[Source](https://github.com/nerdvegas/rez/tree/2.85.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.84.0...2.85.0)

**Merged pull requests:**

- Let rez-selftest try using pytest [\#1051](https://github.com/nerdvegas/rez/pull/1051) ([davidlatwe](https://github.com/davidlatwe))

## 2.84.0 (2021-04-16)
[Source](https://github.com/nerdvegas/rez/tree/2.84.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.83.0...2.84.0)

**Notes**

New tool: `rez-rm`.

**Merged pull requests:**

- package removal [\#1063](https://github.com/nerdvegas/rez/pull/1063) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- add package removal [\#1062](https://github.com/nerdvegas/rez/issues/1062)

## 2.83.0 (2021-04-14)
[Source](https://github.com/nerdvegas/rez/tree/2.83.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.82.0...2.83.0)

**Notes**

New tool: `rez-mv`.

**Merged pull requests:**

- Package move [\#1061](https://github.com/nerdvegas/rez/pull/1061) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- add pkg move feature [\#1059](https://github.com/nerdvegas/rez/issues/1059)

## 2.82.0 (2021-04-08)
[Source](https://github.com/nerdvegas/rez/tree/2.82.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.81.2...2.82.0)

**Notes**

New tool: `rez-pkg-ignore`.

**Merged pull requests:**

- Issue 1052 pkg ignore [\#1054](https://github.com/nerdvegas/rez/pull/1054) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- make package ignore a formal api/tool [\#1052](https://github.com/nerdvegas/rez/issues/1052)

## 2.81.2 (2021-04-08)
[Source](https://github.com/nerdvegas/rez/tree/2.81.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.81.1...2.81.2)

**Closed issues:**

- install related regression in v2.80.0 [\#1057](https://github.com/nerdvegas/rez/issues/1057)

## 2.81.1 (2021-04-08)
[Source](https://github.com/nerdvegas/rez/tree/2.81.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.81.0...2.81.1)

**Notes**

CMake no longer uses the `-d` arg to specify the directory in which to find CMakeLists.txt. This appears
to be incompatible with newer cmake versions, but (happily) dropping it in older versions also appears
compatible.

**Merged pull requests:**

- Issue 1055 failing tests [\#1056](https://github.com/nerdvegas/rez/pull/1056) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- problem with alias in powershell [\#1017](https://github.com/nerdvegas/rez/issues/1017)
- tests failing suddenly [\#1055](https://github.com/nerdvegas/rez/issues/1055)

## 2.81.0 (2021-04-01)
[Source](https://github.com/nerdvegas/rez/tree/2.81.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.80.0...2.81.0)

**Merged pull requests:**

- Flake8 [\#1050](https://github.com/nerdvegas/rez/pull/1050) ([nerdvegas](https://github.com/nerdvegas))

## 2.80.0 (2021-03-30)
[Source](https://github.com/nerdvegas/rez/tree/2.80.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.79.1...2.80.0)

**Merged pull requests:**

- Fix rez-python arg disordered [\#1041](https://github.com/nerdvegas/rez/pull/1041) ([davidlatwe](https://github.com/davidlatwe))

## 2.79.1 (2021-03-30)
[Source](https://github.com/nerdvegas/rez/tree/2.79.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.79.0...2.79.1)

**Merged pull requests:**

- Fix sorting of rules with and without family (closes #1037) [\#1038](https://github.com/nerdvegas/rez/pull/1038) ([jasperges](https://github.com/jasperges))

**Closed issues:**

- An exception is raised when combining filters with `-` and without `-`. [\#1037](https://github.com/nerdvegas/rez/issues/1037)

## 2.79.0 (2021-03-30)
[Source](https://github.com/nerdvegas/rez/tree/2.79.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.78.1...2.79.0)

**Merged pull requests:**

- add optionvars [\#1036](https://github.com/nerdvegas/rez/pull/1036) ([davidlatwe](https://github.com/davidlatwe))

## 2.78.1 (2021-03-30)
[Source](https://github.com/nerdvegas/rez/tree/2.78.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.78.0...2.78.1)

**Merged pull requests:**

- auto benchmarking fix [\#1049](https://github.com/nerdvegas/rez/pull/1049) ([nerdvegas](https://github.com/nerdvegas))

## 2.78.0 (2021-03-27)
[Source](https://github.com/nerdvegas/rez/tree/2.78.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.77.1...2.78.0)

**Merged pull requests:**

- Issue 1044 auto benchmarking [\#1048](https://github.com/nerdvegas/rez/pull/1048) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- automatically run benchmarking [\#1044](https://github.com/nerdvegas/rez/issues/1044)

## 2.77.1 (2021-03-16)
[Source](https://github.com/nerdvegas/rez/tree/2.77.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.77.0...2.77.1)

**Merged pull requests:**

- Fix missing files in sdist [\#1042](https://github.com/nerdvegas/rez/pull/1042) ([davidlatwe](https://github.com/davidlatwe))

## 2.77.0 (2021-03-09)
[Source](https://github.com/nerdvegas/rez/tree/2.77.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.76.0...2.77.0)

**Merged pull requests:**

- Adds more variables to the custom build system. [\#1013](https://github.com/nerdvegas/rez/pull/1013) ([bfloch](https://github.com/bfloch))

## 2.76.0 (2021-03-09)
[Source](https://github.com/nerdvegas/rez/tree/2.76.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.75.1...2.76.0)

**Merged pull requests:**

- add EphemeralsBinding.get_range [\#1030](https://github.com/nerdvegas/rez/pull/1030) ([davidlatwe](https://github.com/davidlatwe))

## 2.75.1 (2021-03-09)
[Source](https://github.com/nerdvegas/rez/tree/2.75.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.75.0...2.75.1)

**Merged pull requests:**

- fix rez_bin_path on windows [\#1031](https://github.com/nerdvegas/rez/pull/1031) ([nerdvegas](https://github.com/nerdvegas))
- Fix rez.vendor.distlib for Windows [\#1035](https://github.com/nerdvegas/rez/pull/1035) ([davidlatwe](https://github.com/davidlatwe))

**Closed issues:**

- Issues with system.System.is_production_rez_install method on Windows. [\#1005](https://github.com/nerdvegas/rez/issues/1005)

## 2.75.0 (2021-03-03)
[Source](https://github.com/nerdvegas/rez/tree/2.74.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.73.0...2.75.0)

**Notes**

* Workflow added to perform pypi publish on release
* Wiki workflow updated to publish only on release
* Note that version skip (2.73.0 -> 2.75.0) due to workflow testing on github

**Merged pull requests:**

- Issue 1032 pypi [\#1034](https://github.com/nerdvegas/rez/pull/1034) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- Pypi entries are out of date [\#1032](https://github.com/nerdvegas/rez/issues/1032)

## 2.73.0 (2021-03-02)
[Source](https://github.com/nerdvegas/rez/tree/2.73.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.72.5...2.73.0)

**Merged pull requests:**

- context bundles [\#1029](https://github.com/nerdvegas/rez/pull/1029) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- bundled contexts ("bundles") [\#1009](https://github.com/nerdvegas/rez/issues/1009)

## 2.72.5 (2021-03-02)
[Source](https://github.com/nerdvegas/rez/tree/2.72.5) | [Diff](https://github.com/nerdvegas/rez/compare/2.72.4...2.72.5)

**Merged pull requests:**

- Improve get_variant_from_uri on Windows [\#1011](https://github.com/nerdvegas/rez/pull/1011) ([davidlatwe](https://github.com/davidlatwe))

## 2.72.4 (2021-03-02)
[Source](https://github.com/nerdvegas/rez/tree/2.72.4) | [Diff](https://github.com/nerdvegas/rez/compare/2.72.3...2.72.4)

**Merged pull requests:**

- Wait subprocess cleanup [\#1010](https://github.com/nerdvegas/rez/pull/1010) ([davidlatwe](https://github.com/davidlatwe))

## 2.72.3 (2021-02-23)
[Source](https://github.com/nerdvegas/rez/tree/2.72.3) | [Diff](https://github.com/nerdvegas/rez/compare/2.72.2...2.72.3)

**Merged pull requests:**

- Fix tab-completion behavior for rez deployments installed with python3 [\#1021](https://github.com/nerdvegas/rez/pull/1021) ([zachlewis](https://github.com/zachlewis))

**Closed issues:**

- Tab completion broken for rez deployments installed with Python-3.6 [\#1020](https://github.com/nerdvegas/rez/issues/1020)

## 2.72.2 (2021-02-23)
[Source](https://github.com/nerdvegas/rez/tree/2.72.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.72.1...2.72.2)

**Merged pull requests:**

- Fix install-as-rez-package script for Windows [\#1014](https://github.com/nerdvegas/rez/pull/1014) ([davidlatwe](https://github.com/davidlatwe))

## 2.72.1 (2021-02-23)
[Source](https://github.com/nerdvegas/rez/tree/2.72.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.72.0...2.72.1)

**Merged pull requests:**

- Fix dir/file remove error handling [\#1012](https://github.com/nerdvegas/rez/pull/1012) ([davidlatwe](https://github.com/davidlatwe))
- Fixes bug where readlink is applied on regular files. [\#1019](https://github.com/nerdvegas/rez/pull/1019) ([bfloch](https://github.com/bfloch))

## 2.72.0 (2021-01-12)
[Source](https://github.com/nerdvegas/rez/tree/2.72.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.71.0...2.72.0)

**Notes**

This release uses python-3's native `venv` module to perform the rez installation, for python-3.7 and above.
For earlier python versions, an embedded copy of virtualenv was used, but this ceases to work correctly in
python-3.9.

**Merged pull requests:**

- venv based install [\#1006](https://github.com/nerdvegas/rez/pull/1006) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- Installation With Python >=3.9 Fails ('HTMLParser' object has no attribute 'unescape') [\#980](https://github.com/nerdvegas/rez/issues/980)
- have install.py use venv in python3 [\#982](https://github.com/nerdvegas/rez/issues/982)

## 2.71.0 (2020-12-29)
[Source](https://github.com/nerdvegas/rez/tree/2.71.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.70.5...2.71.0)

**Notes**

[Ephemeral packages](https://github.com/nerdvegas/rez/wiki/Ephemeral-Packages) are a major new feature. These
enable dependencies on abstract objects or machine capabilities (for example), and also act as a way to pass
'options' to packages that can alter their behaviour. These will also form the basis for _package features_, an
upcoming feature that will allow packages to depend on _features_ of other packages, rather than just their
version number.

**Merged pull requests:**

- Ephemeral packages [\#993](https://github.com/nerdvegas/rez/pull/993) ([nerdvegas](https://github.com/nerdvegas))

## 2.70.5 (2020-12-29)
[Source](https://github.com/nerdvegas/rez/tree/2.70.5) | [Diff](https://github.com/nerdvegas/rez/compare/2.70.4...2.70.5)

**Merged pull requests:**

- Fix module 'Qt.QtWidgets' has no attribute'QPainter' [\#992](https://github.com/nerdvegas/rez/pull/992) ([loonghao](https://github.com/loonghao))

## 2.70.4 (2020-12-29)
[Source](https://github.com/nerdvegas/rez/tree/2.70.4) | [Diff](https://github.com/nerdvegas/rez/compare/2.70.3...2.70.4)

**Merged pull requests:**

- update open_file_for_write with simplified error handling [\#998](https://github.com/nerdvegas/rez/pull/998) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- 'rez build --install --prefix' error  [\#858](https://github.com/nerdvegas/rez/issues/858)

## 2.70.3 (2020-12-29)
[Source](https://github.com/nerdvegas/rez/tree/2.70.3) | [Diff](https://github.com/nerdvegas/rez/compare/2.70.2...2.70.3)

**Merged pull requests:**

- Fix no CLI args passed into forward script on Windows [\#990](https://github.com/nerdvegas/rez/pull/990) ([davidlatwe](https://github.com/davidlatwe))

## 2.70.2 (2020-12-29)
[Source](https://github.com/nerdvegas/rez/tree/2.70.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.70.1...2.70.2)

**Merged pull requests:**

- fix: exit file write retry loop after successfull write [\#989](https://github.com/nerdvegas/rez/pull/989) ([bpabel](https://github.com/bpabel))

## 2.70.1 (2020-12-29)
[Source](https://github.com/nerdvegas/rez/tree/2.70.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.70.0...2.70.1)

**Merged pull requests:**

- Fixes release hook for Python 3 [\#981](https://github.com/nerdvegas/rez/pull/981) ([bfloch](https://github.com/bfloch))

## 2.70.0 (2020-12-29)
[Source](https://github.com/nerdvegas/rez/tree/2.70.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.7...2.70.0)

**Backwards Compatibility Issues**

This release **removes the bez build system**. This was a very simple build system that does nothing more
than call a function in `rezbuild.py`, passing it some build attributes (such as installation path). It has
been removed because you can achieve the same thing using a custom build command, and you can retrieve the
build attributes from environment variables instead.

If you attempt to build a package that was previously using bez (ie, the `rezbuild.py` script is still there,
and `build_command` is not specified in your package.py) then the resulting error message shows you what you
need to do to port your existing build script.

**Merged pull requests:**

- Remove bez [\#979](https://github.com/nerdvegas/rez/pull/979) ([nerdvegas](https://github.com/nerdvegas))

## 2.69.7 (2020-12-22)
[Source](https://github.com/nerdvegas/rez/tree/2.69.7) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.6...2.69.7)

**Merged pull requests:**

- Issue 994 wiki workflow fixes [\#995](https://github.com/nerdvegas/rez/pull/995) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- wiki workflow broken [\#994](https://github.com/nerdvegas/rez/issues/994)

## 2.69.6 (2020-11-24)
[Source](https://github.com/nerdvegas/rez/tree/2.69.6) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.5...2.69.6)

**Merged pull requests:**

- avoid using fileConfig to init logging, as it overwrites root logger [\#978](https://github.com/nerdvegas/rez/pull/978) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- rez overwrites root logger [\#977](https://github.com/nerdvegas/rez/issues/977)

## 2.69.5 (2020-11-19)
[Source](https://github.com/nerdvegas/rez/tree/2.69.5) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.4...2.69.5)

**Merged pull requests:**

- Try telling who is/are requesting missing package [\#976](https://github.com/nerdvegas/rez/pull/976) ([davidlatwe](https://github.com/davidlatwe))

## 2.69.4 (2020-11-17)
[Source](https://github.com/nerdvegas/rez/tree/2.69.4) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.3...2.69.4)

**Merged pull requests:**

- Fix pip.py get purelib error. [\#973](https://github.com/nerdvegas/rez/pull/973) ([zclongpop123](https://github.com/zclongpop123))

## 2.69.3 (2020-11-17)
[Source](https://github.com/nerdvegas/rez/tree/2.69.3) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.2...2.69.3)

**Merged pull requests:**

- handling QFileDialog.getSaveFileName return type [\#963](https://github.com/nerdvegas/rez/pull/963) ([sparklabor](https://github.com/sparklabor))

**Closed issues:**

- QFileDialog.getSaveFileName and getOpenFileName return tuple not str [\#962](https://github.com/nerdvegas/rez/issues/962)

## 2.69.2 (2020-11-17)
[Source](https://github.com/nerdvegas/rez/tree/2.69.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.1...2.69.2)

**Merged pull requests:**

- 965| Fix io.UnsupportedOperation [\#966](https://github.com/nerdvegas/rez/pull/966) ([spsalefeve](https://github.com/spsalefeve))

**Closed issues:**

- io.UnsupportedOperation when using rez api with pytest [\#965](https://github.com/nerdvegas/rez/issues/965)

## 2.69.1 (2020-11-17)
[Source](https://github.com/nerdvegas/rez/tree/2.69.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.69.0...2.69.1)

**Merged pull requests:**

- Update vendored pydot (1.4.2.dev0) [\#970](https://github.com/nerdvegas/rez/pull/970) ([davidlatwe](https://github.com/davidlatwe))

## 2.69.0 (2020-11-17)
[Source](https://github.com/nerdvegas/rez/tree/2.69.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.68.5...2.69.0)

**Merged pull requests:**

- Fix forwarding script on Windows (suite supporting) [\#968](https://github.com/nerdvegas/rez/pull/968) ([davidlatwe](https://github.com/davidlatwe))

## 2.68.5 (2020-10-06)
[Source](https://github.com/nerdvegas/rez/tree/2.68.5) | [Diff](https://github.com/nerdvegas/rez/compare/2.68.4...2.68.5)

**Merged pull requests:**

- Handling build/install directory remove error in build process [\#959](https://github.com/nerdvegas/rez/pull/959) ([davidlatwe](https://github.com/davidlatwe))

## 2.68.4 (2020-10-06)
[Source](https://github.com/nerdvegas/rez/tree/2.68.4) | [Diff](https://github.com/nerdvegas/rez/compare/2.68.3...2.68.4)

**Merged pull requests:**

- Support rez-env -c <alias> or -- <alias> (Windows CMD shell) [\#948](https://github.com/nerdvegas/rez/pull/948) ([davidlatwe](https://github.com/davidlatwe))

**Closed issues:**

- Alias can't be used on the same line as rez-env [\#708](https://github.com/nerdvegas/rez/issues/708)

## 2.68.3 (2020-09-22)
[Source](https://github.com/nerdvegas/rez/tree/2.68.3) | [Diff](https://github.com/nerdvegas/rez/compare/2.68.0...2.68.3)

**Merged pull requests:**

- fix regression wrt unicode, subprocess [\#961](https://github.com/nerdvegas/rez/pull/961) ([nerdvegas](https://github.com/nerdvegas))

- Fix unicode vcs changelog encode err [\#956](https://github.com/nerdvegas/rez/pull/956) ([davidlatwe](https://github.com/davidlatwe))

- Fix repo location false mismatch [\#957](https://github.com/nerdvegas/rez/pull/957) ([davidlatwe](https://github.com/davidlatwe))

## 2.68.0 (2020-09-22)
[Source](https://github.com/nerdvegas/rez/tree/2.68.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.67.1...2.68.0)

**Backwards Compatibility Issues**

Note that this release changes OS detection on linux. The results _should_ be the same, but if they
do differ, and you need to retain the same OS name (which you probably will, because you'll have
packages that depend on the analogous implicit package), then you can use the
[platform_map](https://github.com/nerdvegas/rez/wiki/Configuring-Rez#platform_map) setting.

**Merged pull requests:**

- Replace platform.linux_distribution by distro [\#954](https://github.com/nerdvegas/rez/pull/954) ([predat](https://github.com/predat))

**Closed issues:**

- rez platform_ broken with python3.8 [\#883](https://github.com/nerdvegas/rez/issues/883)

## 2.67.1 (2020-09-11)
[Source](https://github.com/nerdvegas/rez/tree/2.67.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.67.0...2.67.1)

**Merged pull requests:**

- made this.root visible to pkg preprocessor [\#953](https://github.com/nerdvegas/rez/pull/953) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- this.root is None in package preprocessor [\#952](https://github.com/nerdvegas/rez/issues/952)

## 2.67.0 (2020-08-25)
[Source](https://github.com/nerdvegas/rez/tree/2.67.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.66.1...2.67.0)

**Merged pull requests:**

- Ninja support [\#940](https://github.com/nerdvegas/rez/pull/940) ([bareya](https://github.com/bareya))
- print warning once if pkg cache dir not present [\#942](https://github.com/nerdvegas/rez/pull/942) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- don't raise on missing package cache dir [\#941](https://github.com/nerdvegas/rez/issues/941)

## 2.66.1 (2020-08-25)
[Source](https://github.com/nerdvegas/rez/tree/2.66.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.66.0...2.66.1)

**Merged pull requests:**

- Fix #934, no hash string in include script file name [\#935](https://github.com/nerdvegas/rez/pull/935) ([davidlatwe](https://github.com/davidlatwe))
- Raise unversioned error when config not allowed [\#938](https://github.com/nerdvegas/rez/pull/938) ([davidlatwe](https://github.com/davidlatwe))

**Closed issues:**

- Installed package not including latest module [\#934](https://github.com/nerdvegas/rez/issues/934)

## 2.66.0 (2020-08-11)
[Source](https://github.com/nerdvegas/rez/tree/2.66.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.65.0...2.66.0)

**Merged pull requests:**

- [docs] Sphinx API hosted on GitHub Pages [\#832](https://github.com/nerdvegas/rez/pull/832) ([j0yu](https://github.com/j0yu))

## 2.65.0 (2020-08-11)
[Source](https://github.com/nerdvegas/rez/tree/2.65.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.64.0...2.65.0)

**Notes**

This release cleans up the wiki-based doc generation code, and adds a github workflow
to automatically update the wiki.

**Merged pull requests:**

- [wiki] Move update utils into main repo [\#831](https://github.com/nerdvegas/rez/pull/831) ([j0yu](https://github.com/j0yu))

## 2.64.0 (2020-08-11)
[Source](https://github.com/nerdvegas/rez/tree/2.64.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.63.0...2.64.0)

**Merged pull requests:**

- added DelayLoad config primitive [\#922](https://github.com/nerdvegas/rez/pull/922) ([nerdvegas](https://github.com/nerdvegas))
- Sort keys in resolved context JSON [\#923](https://github.com/nerdvegas/rez/pull/923) ([dbr](https://github.com/dbr))
- Respect sys path order when spawning shell on Windows [\#926](https://github.com/nerdvegas/rez/pull/926) ([davidlatwe](https://github.com/davidlatwe))
- Fix #927, add encoding=utf-8 on file write [\#928](https://github.com/nerdvegas/rez/pull/928) ([davidlatwe](https://github.com/davidlatwe))

**Closed issues:**

- add 'delay_load' config primitive [\#921](https://github.com/nerdvegas/rez/issues/921)
- New spawned shell's `PATH` is random ordered on Windows [\#925](https://github.com/nerdvegas/rez/issues/925)
- Packages that contains Unicode character failed on install/release [\#927](https://github.com/nerdvegas/rez/issues/927)

## 2.63.0 (2020-08-04)
[Source](https://github.com/nerdvegas/rez/tree/2.63.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.62.0...2.63.0)

**Merged pull requests:**

- don't attempt to update pkg cache on failed resolve [\#916](https://github.com/nerdvegas/rez/pull/916) ([nerdvegas](https://github.com/nerdvegas))
- fix pkg cache fail on windows, py<=2.7 [\#917](https://github.com/nerdvegas/rez/pull/917) ([nerdvegas](https://github.com/nerdvegas))
- raise metadata error on bad pkg, rather than build-system-notfound [\#918](https://github.com/nerdvegas/rez/pull/918) ([nerdvegas](https://github.com/nerdvegas))
- default to disable package caching during build [\#920](https://github.com/nerdvegas/rez/pull/920) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- rez-packaage-cache issue on conflicting context [\#905](https://github.com/nerdvegas/rez/issues/905)
- Package caching does not work on windows due to device not being implemented in py2 on Windows [\#912](https://github.com/nerdvegas/rez/issues/912)
- Miss-leaded error message while building with invalid package metadata [\#915](https://github.com/nerdvegas/rez/issues/915)
- add ability to disable pkg caching during build [\#919](https://github.com/nerdvegas/rez/issues/919)

## 2.62.0 (2020-07-22)
[Source](https://github.com/nerdvegas/rez/tree/2.62.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.61.1...2.62.0)

**Merged pull requests:**

- Allow configuration of filesystem lock mechanism [\#903](https://github.com/nerdvegas/rez/pull/903) ([dbr](https://github.com/dbr))
- make context tracking tolerant of errors [\#911](https://github.com/nerdvegas/rez/pull/911) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- SSL crash related to context tracking [\#910](https://github.com/nerdvegas/rez/issues/910)

## 2.61.1 (2020-07-10)
[Source](https://github.com/nerdvegas/rez/tree/2.61.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.61.0...2.61.1)

**Merged pull requests:**

- fix for rez occasionally installed into lib64 dir [\#902](https://github.com/nerdvegas/rez/pull/902) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- occasional missing rez cli in rez-env [\#901](https://github.com/nerdvegas/rez/issues/901)

## 2.61.0 (2020-07-10)
[Source](https://github.com/nerdvegas/rez/tree/2.61.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.60.1...2.61.0)

**Notes**

Package caching feature added, see [here](https://github.com/nerdvegas/rez/wiki/Package-Caching).

**Merged pull requests:**

- Package cache [\#893](https://github.com/nerdvegas/rez/pull/893) ([nerdvegas](https://github.com/nerdvegas))

## 2.60.1 (2020-05-23)
[Source](https://github.com/nerdvegas/rez/tree/2.60.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.60.0...2.60.1)

**Merged pull requests:**

- fix bug in py3 (hash of unicode) [\#888](https://github.com/nerdvegas/rez/pull/888) ([nerdvegas](https://github.com/nerdvegas))
- fix context serilisation wrt append_sys_path [\#890](https://github.com/nerdvegas/rez/pull/890) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- context sourcing broken (ResolvedContext.append_sys_path not serialised) [\#889](https://github.com/nerdvegas/rez/issues/889)

## 2.60.0 (2020-05-12)
[Source](https://github.com/nerdvegas/rez/tree/2.60.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.59.1...2.60.0)

**Backwards Compatibility Issues**

Please note that #887 introduces a subtle change to CLI behaviour. Previously, `rez-context --resolve`
would print a space-separated list of packages, even when piped to another process. Now however, if
the output is piped, it will print one package per line. This is an improvement, as it means you can
more easily chain `rez-context` with other utilities such as grep, xargs etc.

**Merged pull requests:**

- added get_variant_from_uri functionality [\#886](https://github.com/nerdvegas/rez/pull/886) ([nerdvegas](https://github.com/nerdvegas))
- Cli variant uri [\#887](https://github.com/nerdvegas/rez/pull/887) ([nerdvegas](https://github.com/nerdvegas))

## 2.59.1 (2020-05-09)
[Source](https://github.com/nerdvegas/rez/tree/2.59.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.59.0...2.59.1)

**Merged pull requests:**

- fixed - rez-context -g with prune-package fails [\#885](https://github.com/nerdvegas/rez/pull/885) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- rez-context -g with prune-package fails [\#884](https://github.com/nerdvegas/rez/issues/884)

## 2.59.0 (2020-04-30)
[Source](https://github.com/nerdvegas/rez/tree/2.59.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.58.1...2.59.0)

**Merged pull requests:**

- Fix issue 826 - correct python and pip fallback [\#878](https://github.com/nerdvegas/rez/pull/878) ([j0yu](https://github.com/j0yu))

**Closed issues:**

- rez-pip issues finding pip executable [\#826](https://github.com/nerdvegas/rez/issues/826)

## 2.58.1 (2020-04-22)
[Source](https://github.com/nerdvegas/rez/tree/2.58.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.58.0...2.58.1)

**Merged pull requests:**

- Fix ISSUE-879: AttributeError: 'Namespace' object has no attribute 'func' [\#880](https://github.com/nerdvegas/rez/pull/880) ([rfletchr](https://github.com/rfletchr))

**Closed issues:**

- AttributeError: 'Namespace' object has no attribute 'func' [\#879](https://github.com/nerdvegas/rez/issues/879)

## 2.58.0 (2020-04-15)
[Source](https://github.com/nerdvegas/rez/tree/2.58.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.57.0...2.58.0)

**Merged pull requests:**

- Expose package orderers in rez config [\#868](https://github.com/nerdvegas/rez/pull/868) ([rlessardrodeofx](https://github.com/rlessardrodeofx))

**Closed issues:**

- add configurability of package orderers [\#329](https://github.com/nerdvegas/rez/issues/329)

## 2.57.0 (2020-04-14)
[Source](https://github.com/nerdvegas/rez/tree/2.57.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.56.2...2.57.0)

**Merged pull requests:**

- Added distribution author and help information [\#873](https://github.com/nerdvegas/rez/pull/873) ([ColinKennedy](https://github.com/ColinKennedy))

**Closed issues:**

- rez-pip - Add help / authors attributes [\#838](https://github.com/nerdvegas/rez/issues/838)

## 2.56.2 (2020-04-14)
[Source](https://github.com/nerdvegas/rez/tree/2.56.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.56.1...2.56.2)

**Merged pull requests:**

- Fix for git rev-parse error out before checking for allow_no_upstream [\#872](https://github.com/nerdvegas/rez/pull/872) ([alexxbb](https://github.com/alexxbb))

**Closed issues:**

- override git plugin config in package.py [\#871](https://github.com/nerdvegas/rez/issues/871)

## 2.56.1 (2020-03-31)
[Source](https://github.com/nerdvegas/rez/tree/2.56.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.56.0...2.56.1)

**Merged pull requests:**

- Log during pip install [\#867](https://github.com/nerdvegas/rez/pull/867) ([j0yu](https://github.com/j0yu))

## 2.56.0 (2020-03-31)
[Source](https://github.com/nerdvegas/rez/tree/2.56.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.55.0...2.56.0)

**Merged pull requests:**

- pip install path remap [\#866](https://github.com/nerdvegas/rez/pull/866) ([j0yu](https://github.com/j0yu))

**Closed issues:**

- rez-pip - no case for ../../include/... file [\#861](https://github.com/nerdvegas/rez/issues/861)

## 2.55.0 (2020-03-21)
[Source](https://github.com/nerdvegas/rez/tree/2.55.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.54.0...2.55.0)

**Merged pull requests:**

- Fixed bug in test variant selection [\#842](https://github.com/nerdvegas/rez/pull/842) ([nerdvegas](https://github.com/nerdvegas))
- pre_test_commands [\#844](https://github.com/nerdvegas/rez/pull/844) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- tests "on_variants" not working as expected in some cases [\#841](https://github.com/nerdvegas/rez/issues/841)
- pre_test_commands [\#843](https://github.com/nerdvegas/rez/issues/843)

## 2.54.0 (2020-02-20)
[Source](https://github.com/nerdvegas/rez/tree/2.54.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.53.1...2.54.0)

**Merged pull requests:**

- Install as package part2 [\#845](https://github.com/nerdvegas/rez/pull/845) ([nerdvegas](https://github.com/nerdvegas))
- Allow absolute path for build directory [\#853](https://github.com/nerdvegas/rez/pull/853) ([joehigham-bss](https://github.com/joehigham-bss))
- [rez-pip] Fix for ptvsd install [\#855](https://github.com/nerdvegas/rez/pull/855) ([j0yu](https://github.com/j0yu))

**Closed issues:**

- "rez-pip -i ptvsd" produces bad package [\#821](https://github.com/nerdvegas/rez/issues/821)

## 2.53.1 (2020-02-12)
[Source](https://github.com/nerdvegas/rez/tree/2.53.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.53.0...2.53.1)

**Notes**

Misc Python-3 related issues.

**Merged pull requests:**

- PR: Fix "StringIO" imports and accesses. [\#850](https://github.com/nerdvegas/rez/pull/850) ([KelSolaar](https://github.com/KelSolaar))
- PR: Use "QtCompat" to handle "QHeaderView" incompatibilities and fix broken "resolve" button in "rez-gui". [\#851](https://github.com/nerdvegas/rez/pull/851) ([KelSolaar](https://github.com/KelSolaar))

**Closed issues:**

- "ImportError" exception raised while using "rez-gui" in Python 3. [\#848](https://github.com/nerdvegas/rez/issues/848)
- "AttributeError" exception raised when using "rez-gui" Package Browser with Pyside2 . [\#849](https://github.com/nerdvegas/rez/issues/849)

## 2.53.0 (2020-02-04)
[Source](https://github.com/nerdvegas/rez/tree/2.53.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.52.2...2.53.0)

**Merged pull requests:**

- [Feature] Add rez-pip extra args passthrough [\#827](https://github.com/nerdvegas/rez/pull/827) ([lambdaclan](https://github.com/lambdaclan))

**Closed issues:**

- rez-pip creates .pyc files by default [\#816](https://github.com/nerdvegas/rez/issues/816)

## 2.52.2 (2020-01-31)
[Source](https://github.com/nerdvegas/rez/tree/2.52.2) | [Diff](https://github.com/nerdvegas/rez/compare/2.52.1...2.52.2)

**Merged pull requests:**

- deprecate trailing underscored sourcefiles [\#839](https://github.com/nerdvegas/rez/pull/839) ([nerdvegas](https://github.com/nerdvegas))
- Minor pr3 fixes [\#840](https://github.com/nerdvegas/rez/pull/840) ([nerdvegas](https://github.com/nerdvegas))

## 2.52.1 (2020-01-21)
[Source](https://github.com/nerdvegas/rez/tree/2.52.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.52.0...2.52.1)

**Merged pull requests:**

- added new env vars - REZ_SHELL_INIT_TIMESTAMP, REZ_SHELL_INTERACTIVE [\#834](https://github.com/nerdvegas/rez/pull/834) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- add env-var to record shell init time [\#833](https://github.com/nerdvegas/rez/issues/833)

## 2.52.0 (2020-01-18)
[Source](https://github.com/nerdvegas/rez/tree/2.52.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.51.0...2.52.0)

**Notes**

Adds a new [pre_build_commands](https://github.com/nerdvegas/rez/wiki/Package-Commands#pre-build-commands)
package.py attribute, for adding runtime build configuration.

**Merged pull requests:**

- Rep002 pre build commands [\#825](https://github.com/nerdvegas/rez/pull/825) ([nerdvegas](https://github.com/nerdvegas))

## 2.51.0 (2020-01-18)
[Source](https://github.com/nerdvegas/rez/tree/2.51.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.50.0...2.51.0)

**Notes**

This release goes a large way to implementing [REP-001](https://github.com/nerdvegas/rez/issues/665)

Includes:
- Pre-install/release running of package tests;
- New rez-test `--inplace` option;
- Correct iteration of tests over variants (variant iteration did not previously exist)

Still to do:
- rez-test `--interactive` option;
- rez-test 'development' mode.

**Merged pull requests:**

- Rep001 1 (rez-test improvements) [\#807](https://github.com/nerdvegas/rez/pull/807) ([nerdvegas](https://github.com/nerdvegas))
- Rep001 2 hooks [\#811](https://github.com/nerdvegas/rez/pull/811) ([nerdvegas](https://github.com/nerdvegas))

## 2.50.0 (2019-12-12)
[Source](https://github.com/nerdvegas/rez/tree/2.50.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.49.0...2.50.0)

**Merged pull requests:**

- removed odd case of _Bound instantiation with Version [\#815](https://github.com/nerdvegas/rez/pull/815) ([nerdvegas](https://github.com/nerdvegas))
- memcached incompatibility fix [\#818](https://github.com/nerdvegas/rez/pull/818) ([nerdvegas](https://github.com/nerdvegas))
- Bug/819 enable colorization on windows [\#820](https://github.com/nerdvegas/rez/pull/820) ([instinct-vfx](https://github.com/instinct-vfx))

**Closed issues:**

- potential memcached client incompatibility [\#817](https://github.com/nerdvegas/rez/issues/817)
- Remove hard prevention of colorization on windows [\#819](https://github.com/nerdvegas/rez/issues/819)

## 2.49.0 (2019-12-05)
[Source](https://github.com/nerdvegas/rez/tree/2.49.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.48.1...2.49.0)

**Merged pull requests:**

- Migrate rezgui.qt imports to Qt.py [\#804](https://github.com/nerdvegas/rez/pull/804) ([douglaslassance](https://github.com/douglaslassance))

## 2.48.1 (2019-12-05)
[Source](https://github.com/nerdvegas/rez/tree/2.48.1) | [Diff](https://github.com/nerdvegas/rez/compare/2.48.0...2.48.1)

**Merged pull requests:**

- Fixes #792 cmd empty echo [\#793](https://github.com/nerdvegas/rez/pull/793) ([bfloch](https://github.com/bfloch))

**Closed issues:**

- cmd handles empty echo incorrectly [\#792](https://github.com/nerdvegas/rez/issues/792)

## 2.48.0 (2019-11-26)
[Source](https://github.com/nerdvegas/rez/tree/2.48.0) | [Diff](https://github.com/nerdvegas/rez/compare/2.47.14...2.48.0)

**Merged pull requests:**

- rez.pip: Support python 2 executable on Windows (796) [\#798](https://github.com/nerdvegas/rez/pull/798) ([JeanChristopheMorinPerso](https://github.com/JeanChristopheMorinPerso))
- Feature/add 'prefix' argument to rez-pip [\#802](https://github.com/nerdvegas/rez/pull/802) ([predat](https://github.com/predat))

**Closed issues:**

- find_pip_from_context failing on Windows platform [\#796](https://github.com/nerdvegas/rez/issues/796)

## 2.47.14 (2019-11-13)
[Source](https://github.com/nerdvegas/rez/tree/2.47.14) | [Diff](https://github.com/nerdvegas/rez/compare/2.47.13...2.47.14)

**Notes**

Several Windows CI improvements:
* Base and Py docker images are only rebuilt if necessary;
* Docker hub no longer requires a login to pull the image (meaning that tests now pass on forked PRs);
* Rather than checking out the rez github repo in the image entrypoint, the existing checkout (done
  by the workflow) is bind mounted instead.

With these updates, tests are now passing on all platforms.

**Known Issues**

If the image is changed, there is a delay in the new image becoming available on docker hub (5-10 mins).
If a separate push is made in this time, it can fail, as the Windows test expects to see the new image
(which is tagged by commit).

**Merged pull requests:**

- Windows docker enhancements [\#794](https://github.com/nerdvegas/rez/pull/794) ([bfloch](https://github.com/bfloch))
- Remove the login so that PR work at least for the non-image workflows. [\#795](https://github.com/nerdvegas/rez/pull/795) ([bfloch](https://github.com/bfloch))
- Issue 800 windows ci use checkout [\#801](https://github.com/nerdvegas/rez/pull/801) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- windows ci: Use Actions checkout [\#800](https://github.com/nerdvegas/rez/issues/800)

## 2.47.13 (2019-11-08)
[Source](https://github.com/nerdvegas/rez/tree/2.47.13) | [Diff](https://github.com/nerdvegas/rez/compare/2.47.12...2.47.13)

**Notes**

This release just makes some minor changes related to the CI tests. As well as the changes in the PR shown
below, the following changes were also made:

* 'Windows Docker' workflow was renamed 'Windows'
* MacOS version used in workflow was changed from 10.14 to 'latest', as per Github's instructions (which were
  emailed to me).

**Merged pull requests:**

- Updated actions badges in README [\#786](https://github.com/nerdvegas/rez/pull/786) ([j0yu](https://github.com/j0yu))

**Closed issues:**

- Fix README actions badges not showing current master status [\#785](https://github.com/nerdvegas/rez/issues/785)

## 2.47.12 (2019-11-06)
[Source](https://github.com/nerdvegas/rez/tree/2.47.12) | [Diff](https://github.com/nerdvegas/rez/compare/2.47.11...2.47.12)

**Notes**

This release adds a docker-based workflow for the Github Actions Windows test. This was done specifically
because Github's available Windows runtimes come with an already long %PATH%. Rez adds to PATH and hits
a limit, causing the `cmd` shell to fail in several tests.

**Merged pull requests:**

- Windows Tests via Docker [\#781](https://github.com/nerdvegas/rez/pull/781) ([bfloch](https://github.com/bfloch))

## 2.47.11 (2019-11-06)
[Source](https://github.com/nerdvegas/rez/tree/2.47.11) | [Diff](https://github.com/nerdvegas/rez/compare/2.47.10...2.47.11)

**Merged pull requests:**

- Fixes some failing tests on windows [\#775](https://github.com/nerdvegas/rez/pull/775) ([willjp](https://github.com/willjp))

## 2.47.10 (2019-11-06)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.10) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.9...2.47.10)

**Merged pull requests:**

- Replace Popen with check_output to catch errors in installation [\#778](https://github.com/nerdvegas/rez/pull/778) ([instinct-vfx](https://github.com/instinct-vfx))
- Popen UnicodeDecodeError partial fix [\#779](https://github.com/nerdvegas/rez/pull/779) ([willjp](https://github.com/willjp))
- Unwanted debug printing [\#780](https://github.com/nerdvegas/rez/pull/780) ([predat](https://github.com/predat))

**Closed issues:**

- rez-release UnicodeDecodeError (windows) [\#776](https://github.com/nerdvegas/rez/issues/776)
- Errors in pip installation part go unnoticed by rez install.py [\#777](https://github.com/nerdvegas/rez/issues/777)

## 2.47.9 (2019-10-25)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.9) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.8...2.47.9)

**Merged pull requests:**

- rez.util.ProgressBar checks `Bar.__del__` exists before invocation #769 [\#774](https://github.com/nerdvegas/rez/pull/774) ([willjp](https://github.com/willjp))

**Closed issues:**

- rez-depends -- AttributeError: type object 'Bar' has no attribute '__del__' (win, py-3, rez-2.47.7) [\#769](https://github.com/nerdvegas/rez/issues/769)

## 2.47.8 (2019-10-24)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.8) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.7...2.47.8)

**Merged pull requests:**

- Issue 763 prompt leak [\#767](https://github.com/nerdvegas/rez/pull/767) ([nerdvegas](https://github.com/nerdvegas))
- Fixes cmd due to oversight in 9c8334a106de900964e52f1ed8ee4155acdfe142 [\#770](https://github.com/nerdvegas/rez/pull/770) ([bfloch](https://github.com/bfloch))
- Skip `test_build_cmake` on Windows. [\#772](https://github.com/nerdvegas/rez/pull/772) ([bfloch](https://github.com/bfloch))

**Closed issues:**

- cross-shell prompt leakage can cause error [\#763](https://github.com/nerdvegas/rez/issues/763)

## 2.47.7 (2019-10-22)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.7) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.6...2.47.7)

**Notes**

* Rez-pip: Add a new logic to find which pip will be used to install pip packages.
* Rez-pip: New deprecation warning when --pip-version is used.
* See https://github.com/nerdvegas/rez/wiki/Pip for more details on rez-pip.

**Merged pull requests:**

- rez-pip: Assume pip provided by python package [\#757](https://github.com/nerdvegas/rez/pull/757) ([JeanChristopheMorinPerso](https://github.com/JeanChristopheMorinPerso))

**Closed issues:**

- rez-pip should assume python provided pip [\#706](https://github.com/nerdvegas/rez/issues/706)
- rez-pip python 3 error [\#764](https://github.com/nerdvegas/rez/issues/764)

## 2.47.6 (2019-10-22)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.6) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.5...2.47.6)

**Merged pull requests:**

- Subproc wrapper part2 [\#762](https://github.com/nerdvegas/rez/pull/762) ([nerdvegas](https://github.com/nerdvegas))

**Closed issues:**

- ResourceWarning with ResolvedContext.execute_shell (py3) [\#761](https://github.com/nerdvegas/rez/issues/761)

## 2.47.5 (2019-10-22)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.5) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.4...2.47.5)

**Merged pull requests:**

- revert progress iteration and update vendored [\#766](https://github.com/nerdvegas/rez/pull/766) ([maxnbk](https://github.com/maxnbk))

**Closed issues:**

- rez-depends -- 'ProgressBar' object is not an iterator (py-3, rez-2.47.4) [\#765](https://github.com/nerdvegas/rez/issues/765)

## 2.47.4 (2019-10-11)
[Source](https://github.com/repos/nerdvegas/rez/tree/2.47.4) | [Diff](https://github.com/repos/nerdvegas/rez/compare/2.47.3...2.47.4)

**Notes**

More Python3 compatibility changes.

**Merged pull requests:**

- use subprocess in 'text' mode in most cases [\#753](https://github.com/nerdvegas/rez/pull/753) ([nerdvegas](https://github.com/nerdvegas))
- add __bool__ operator [\#755](https://github.com/nerdvegas/rez/pull/755) ([nerdvegas](https://github.com/nerdvegas))

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
