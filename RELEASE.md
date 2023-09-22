# Releasing New Rez Versions

To release a new version of rez:

1. Merge any PRs in the "Next" milestone.
   * Make a note of the severity of change so that the version number can be semantically versioned.
   * When the version number is known, update the milestone name to the version number.
2. Run the tests (rez-selftest) to double check nothing is broken.
3. Make sure the [rez version](https://github.com/AcademySoftwareFoundation/rez/blob/main/src/rez/utils/_version.py)
   is correct, and change if necessary.
4. Set / Verify that your "origin" remote is set to the actual repository and not your fork.
   * If you don't do this, the release script will push the tag to your fork instead, and you will need to delete it.
5. Update [the changelog](CHANGELOG.md). A handy utility is provided to help you do this.
   To use it, run the following command, replacing X, Y, Z etc with all pull request
   and issue numbers associated with the release:
   ```
   ]$ python ./release-rez.py -c X Y Z
   ```
   This command prints the changelog entry to stdout, which you can then paste in
   to the top of CHANGELOG.md. Add any additional notes as needed.
6. Commit (make sure you sign (`--signoff`) your commit!) and push to `main`.
7. Wait for all Github workflows to pass;
8. Ensure that you have the `GITHUB_RELEASE_REZ_TOKEN` environment variable set to a valid GitHub token.
   * The token will need permission to perform the release on the rez repo.
9. Run the release-rez utility script. This performs the following actions:
   * Creates tag on latest version, and pushes tag to `main`;
   * Generates the new GitHub release (https://github.com/AcademySoftwareFoundation/rez/releases).
   ```
   ]$ python ./release-rez.py
   ```
10. After all workflows and automations complete, check that:
   * The GitHub release was created.
   * The PyPI release was created.
   * The RTD docs were generated successfully.
   * The benchmark workflow successfully pushed results to the repo.
11. Write up an announcement for the ASWF rez Slack channel.
12. Relax.
