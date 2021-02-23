# Releasing New Rez Versions

To merge a PR to master and release a new version:

1. Merge the PR locally, following the instructions given on GitHub in the
   `command line instructions` link (but do not push to master yet);
2. Run the tests (rez-selftest) to double check nothing is broken;
3. Make sure the [rez version](https://github.com/nerdvegas/rez/blob/master/src/rez/utils/_version.py)
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
5. Commit and push to master;
6. Wait for all Github workflows to pass;
7. Run the release-rez utility script. This performs the following actions:
   * Creates tag on latest version, and pushes tag to master;
   * Generates the new GitHub release (https://github.com/nerdvegas/rez/releases).
   ```
   ]$ python ./release-rez.py
   ```
8. Relax.
