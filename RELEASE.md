# Releasing New Rez Versions

If you are a collaborator and have push access to master, these are the steps to
follow to release a new version:

1. Make sure that the version in `utils/_version.py` is updated appropriately.
   Rez uses [semantic versioning](https://semver.org/).
1. Before pushing your branch, update `CHANGELOG.md` to describe the changes. Follow
   the existing structure. The PR for the merge appears in square brackets in the
   title (eg `[#552]`); since this PR doesn't exist yet, just leave `[#XXX]` as a
   placeholder.
2. Push your changes, and create a PR to master. In that PR's description, copy
   the markdown you added to the changelog for this release. Delete the title,
   and use it as the title of the PR instead (with PR link removed).
3. Once approved, merge to master.
4. In master, go back to `CHANGELOG.md` and update the PR number appropriately.
   Push this change, and set the commit message to `changelog patch`.
5. Run tag.sh. This tags the git repo with the version in `utils/_version.py`.
   Then run `git push --tags` to push this new tag.
6. Goto [https://github.com/nerdvegas/rez/releases] and create a new release. Use
   the changelog markdown as the starting point, and format appropriately (look
   at existing release notes to see what to do).

## Example Changelog Entry

```
## 1.2.3 [[#000](https://github.com/nerdvegas/rez/pull/456)] Release Title Here

#### Addressed Issues

* [#000](https://github.com/nerdvegas/rez/issues/000) some thing is broken
* [#001](https://github.com/nerdvegas/rez/issues/001) some other thing is broken

#### Merged PRs

* [#002](https://github.com/nerdvegas/rez/pull/002) fixed the floober
* [#003](https://github.com/nerdvegas/rez/pull/003) added missing flaaber

#### Notes

Notes about the new release go here. These should add any info that isn't
necessarily obvious from the linked issues.

#### COMPATIBILITY ISSUE!

Put any notes here in the unfortunate case where some form of backwards
incompatibility is unavoidable. This is rare.
```
