# Change Log

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
