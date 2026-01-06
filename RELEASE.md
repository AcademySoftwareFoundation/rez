# Release Procedures and standards for rez

## Version nomenclature and release cadence

### The meaning of the version parts

rez releases observe the [semver 2.0.0](https://semver.org/) version numbering standard.
Briefly:

* **MAJOR** version when you make incompatible API changes
* **MINOR** version when you add functionality in a backward compatible manner
* **PATCH** version when you make backward compatible bug fixes

### Cadence of releases

Currently, rez is not considered a component that studios feel the need to
include in the [VFX Reference Platform](https://vfxplatform.com/), although
many do use rez to help manage migrations between and amongst subsequent
iterations thereof.

As such, rez currently releases on an as-needed basis, which is to say, at the
discretion of the TSC. For the most part that means that:

* When there is a bugfix for a recent feature version, releasing a "patch"
bugfix version resolving the issue will be prioritized above new feature
releases.
* When there is a naturally occurring set of features or updates that are
feature-complete, well-tested, self-contained, and ready to go, those will be
released as a "minor" feature update.
* When there is a "major" breaking change, it will be deferred for as reasonably
long as possible. Strategies to make a breaking change into a non-breaking
change will also be asked-for, investigated, and preferred. rez often has
normally gone many years between breaking changes.

## Procedures for Releasing New Rez Versions

To merge a PR to the `main` branch and release a new version:

1. Merge the PR locally, following the instructions given on GitHub in the
   `command line instructions` link (but do not push to `main` yet);
2. Run the tests (rez-selftest) to double check nothing is broken;
3. Make sure the [rez version](https://github.com/AcademySoftwareFoundation/rez/blob/main/src/rez/utils/_version.py)
   is correct, and change if necessary. The version may have been correct at the
   time of PR submission, but may need an update due to releases that have occurred
   since;
4. Update [the changelog](CHANGELOG.md). A handy utility is provided to help you do this.
   To use it, run the following command, replacing X, Y, Z etc with all pull request
   and issue numbers associated with the release:
   ```
   ]$ python ./release-rez.py -c X Y Z
   ```
   This command prints the changelog entry to stdout, which you can then paste in
   to the top of CHANGELOG.md.
5. Commit and push to `main`;
6. Wait for all Github workflows to pass;
7. Run the release-rez utility script. This performs the following actions:
   * Creates tag on latest version, and pushes tag to `main`;
   * Generates the new GitHub release (https://github.com/AcademySoftwareFoundation/rez/releases).
   ```
   ]$ python ./release-rez.py
   ```
8. Relax.
