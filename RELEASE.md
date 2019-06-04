# Releasing New Rez Versions

To merge a PR to master and release a new version:

1. Merge the PR locally, following the instructions given on GitHub in the
   `command line instructions` link (but do not push to master yet);
2. Run the tests (rez-selftest) to double check nothing is broken;
3. Make sure the [rez version](https://github.com/nerdvegas/rez/blob/master/src/rez/utils/_version.py)
   is correct, and change if necessary. The version may have been correct at the
   time of PR submission, but may need an update due to releases that have occurred
   since;
4. Update [the changelog](https://github.com/nerdvegas/rez/blob/master/CHANGELOG.md)
   to include the PR itself, as per existing entries. Also, make sure that the
   date and 'full changelog' link are correct;
5. Push to master;
6. Run `bash tag.sh -p`. This tags the git repo with the version in `utils/_version.py`;
7. Generate the new GitHub release notes, like so:
      ```
      ]$ python ./release_util.py create-release-notes
      ```
   Then, verify the notes have been created correctly - they should appear
   [here](https://github.com/nerdvegas/rez/releases).
8. Relax.
