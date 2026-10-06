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

1. Create a new clone of `git@github.com:AcademySoftwareFoundation/rez`.
   This is preferred over using your existing clone. It will prevent mistakes
   if you have multiple remotes, etc. It also guarantees that you are starting
   from a fresh state that is synced with our repo.
2. Create a new branch that will be used to create a release PR.
3. Update the version in [src/rez/utils/_version.py](src/rez/utils/_version.py)
4. Update [the changelog](CHANGELOG.md). A handy utility is provided to help you do this.

   ```bash
   python release-rez.py changelog
   ```

   This command prints the changelog entry to stdout, which you can then paste in
   to the top of [CHANGELOG.md](CHANGELOG.md).

   Do not keep the output as is. Go over each entry and classify them. You can also
   do editorial changes to make them clearer.

   It is recommended to add a release overview. Create some excitement, thank
   our contributors, explain what the release means, highlight big changes, etc.
5. Run `git shortlog -sne --all` and update the [mailmap](.mailmap) if needed.
6. Commit and create a PR. Then ask your peers from the TSC to review it.
7. Make sure that all CI are passing before merging.
8. Merge in the UI.
9. Switch your local branch to the main branch and pull.
10. Make sure that you are on the main branch and that you have pulled the changes.
11. Create and push the tag
   ```bash
   python ./release-rez.py tag
   ```
12. Look at the tests on GHA for main and the tag. Make sure they all pass.
13. Create the release.
    ```bash
    python release-rez.py release
    ```
    The command will show you what the release will look like (tag, title, release notes).
    It will ask if you really want to release.
14. Go to https://github.com/AcademySoftwareFoundation/rez/actions/workflows/pypi.yaml and
    monitor the release. You will see a new run. Go take a look at the logs and make sure
    that the upload to PyPI works.
15. Go to https://rez.readthedocs.io/en/stable/ and make sure that the stable version
    matches the version you just published.
16. Relax and enjoy!
