# Releasing New Rez Versions

If you are a collaborator and have push access to master, these are the steps to
follow to release a new version:

On your development branch, before creating your PR:

1. Make sure that the version in `utils/_version.py` is updated appropriately.
   Rez uses [semantic versioning](https://semver.org/).
2. Use [this format](https://help.github.com/articles/closing-issues-using-keywords/)
   to mention issue(s) that a commit has fixed. If you don't do this, the
   changelog gets screwed up (it won't list these fixes).
3. Ensure all tests pass (run rez-selftest).

When creating your PR:

1. Don't create it from your master branch - always have a branch dedicated to
   the issue(s) you're addressing.
2. Any issues this PR addresses, that haven't already been mentioned in commits
   as per above, should be listed in the PR description using the same format.
   If you don't do this, the changelog gets screwed up (it won't list these fixes).

After PR is merged to master:

1. Run `bash tag.sh`. This tags the git repo with the version in `utils/_version.py`.
   Then run `git push --tags` to push this new tag.
2. Generate the new changelog entry for this version, like so:
      ```
      ]$ python ./release_util.py create-changelog-entry
      ```
   This writes out the latest changelog entry to LATEST_CHANGELOG.md. Take this
   file, and add the contents to the top of CHANGELOG.md along with whatever minor
   formatting changes are required. If there are any problems (missing/incorrect
   fixed issues) fix them here. If you feel that further description would aid
   in understanding this PR, add it here, directly after the "Full Changelog" link.

   Note that this step can be slow. Go get a coffee.
3. Commit and push the changelog update.
4. Generate the new GitHub release notes, like so:
      ```
      ]$ python ./release_util.py create-release-notes
      ```
   Then verify the notes have been created correctly - they should appear
   [here](https://github.com/nerdvegas/rez/releases).
