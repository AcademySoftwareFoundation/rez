"""
Mercurial version control
"""
from __future__ import print_function
from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSError
from rez.utils.logging_ import print_debug, print_error
import os.path


class HgReleaseVCSError(ReleaseVCSError):
    pass


class HgReleaseVCS(ReleaseVCS):
    @classmethod
    def name(cls):
        return 'hg'

    def __init__(self, pkg_root, vcs_root=None):
        super(HgReleaseVCS, self).__init__(pkg_root, vcs_root=vcs_root)
        self.executable = self.find_executable('hg')

        hgdir = os.path.join(self.vcs_root, '.hg')
        if not os.path.isdir(hgdir):
            raise HgReleaseVCSError(
                "'%s' is not a mercurial working copy" % self.vcs_root)
        try:
            assert self.hg('root')[0] == self.vcs_root
        except AssertionError:
            raise HgReleaseVCSError(
                "'%s' is not the root of a mercurial working copy" % self.vcs_root)
        except Exception as err:
            raise HgReleaseVCSError("failed to call hg binary: " + str(err))

        self.patch_path = os.path.join(hgdir, 'patches')
        if not os.path.isdir(self.patch_path):
            self.patch_path = None

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isdir(os.path.join(path, '.hg'))

    @classmethod
    def search_parents_for_root(cls):
        return True

    def hg(self, *nargs, **kwargs):
        if kwargs.pop('patch', False):
            nargs += ('--mq',)
        if ('-R' not in nargs and '--repository' not in nargs
            and not any(x.startswith(('-R', '--repository=')) for x in nargs)):
            nargs += ('--repository', self.vcs_root)
        if kwargs:
            raise HgReleaseVCSError("Unrecognized keyword args to hg command:"
                                    " %s" % ", ".join(kwargs))
        return self._cmd(self.executable, *nargs)

    def _create_tag_highlevel(self, tag_name, message=None):
        """Create a tag on the toplevel repo if there is no patch repo,
        or a tag on the patch repo and bookmark on the top repo if there is a
        patch repo

        Returns a list where each entry is a dict for each bookmark or tag
        created, which looks like {'type': ('bookmark' or 'tag'), 'patch': bool}
        """
        results = []
        if self.patch_path:
            # make a tag on the patch queue
            tagged = self._create_tag_lowlevel(tag_name, message=message,
                                               patch=True)
            if tagged:
                results.append({'type': 'tag', 'patch': True})

            # use a bookmark on the main repo since we can't change it
            self.hg('bookmark', '-f', tag_name)
            results.append({'type': 'bookmark', 'patch': False})
        else:
            tagged = self._create_tag_lowlevel(tag_name, message=message,
                                               patch=False)
            if tagged:
                results.append({'type': 'tag', 'patch': False})
        return results

    def _create_tag_lowlevel(self, tag_name, message=None, force=True,
                             patch=False):
        """Create a tag on the toplevel or patch repo

        If the tag exists, and force is False, no tag is made. If force is True,
        and a tag exists, but it is a direct ancestor of the current commit,
        and there is no difference in filestate between the current commit
        and the tagged commit, no tag is made. Otherwise, the old tag is
        overwritten to point at the current commit.

        Returns True or False indicating whether the tag was actually committed
        """
        # check if tag already exists, and if it does, if it is a direct
        # ancestor, and there is NO difference in the files between the tagged
        # state and current state
        #
        # This check is mainly to avoid re-creating the same tag over and over
        # on what is essentially the same commit, since tagging will
        # technically create a new commit, and update the working copy to it.
        #
        # Without this check, say you were releasing to three different
        # locations, one right after another; the first would create the tag,
        # and a new tag commit.  The second would then recreate the exact same
        # tag, but now pointing at the commit that made the first tag.
        # The third would create the tag a THIRD time, but now pointing at the
        # commit that created the 2nd tag.
        tags = self.get_tags(patch=patch)

        old_commit = tags.get(tag_name)
        if old_commit is not None:
            if not force:
                return False
            old_rev = old_commit['rev']
            # ok, now check to see if direct ancestor...
            if self.is_ancestor(old_rev, '.', patch=patch):
                # ...and if filestates are same
                altered = self.hg('status', '--rev', old_rev, '--rev', '.',
                                  '--no-status')
                if not altered or altered == ['.hgtags']:
                    force = False
            if not force:
                return False

        tag_args = ['tag', tag_name]
        if message:
            tag_args += ['--message', message]

        # we should be ok with ALWAYS having force flag on now, since we should
        # have already checked if the commit exists.. but be paranoid, in case
        # we've missed some edge case...
        if force:
            tag_args += ['--force']
        self.hg(patch=patch, *tag_args)
        return True

    def get_tags(self, patch=False):
        lines = self.hg('tags', patch=patch)

        # results will look like:
        # tip                              157:2d82ff68b9f5
        # ilmbase-2.1.0                    156:a27f2a7b3375

        # since I don't know if spaces are allowed in tag names, we do an
        # rsplit, once, since we KNOW how the right side should be formatted
        tags = dict(line.rstrip().rsplit(None, 1) for line in lines
                    if line.strip())
        for tag_name, tag_info in tags.items():
            rev, shortnode = tag_info.split(':')
            tags[tag_name] = {'rev': rev, 'shortnode': shortnode}
        return tags

    def tag_exists(self, tag_name):
        tags = self.get_tags()
        return (tag_name in tags.keys())

    def is_ancestor(self, commit1, commit2, patch=False):
        """Returns True if commit1 is a direct ancestor of commit2, or False
        otherwise.

        This method considers a commit to be a direct ancestor of itself"""
        result = self.hg("log", "-r", "first(%s::%s)" % (commit1, commit2),
                         "--template", "exists", patch=patch)
        return "exists" in result

    def get_paths(self, patch=False):
        paths = self.hg("paths", patch=patch)
        return dict(line.split(' = ', 1) for line in paths if line)

    def get_default_url(self, patch=False):
        return self.get_paths(patch=patch).get('default')

    def validate_repostate(self):
        def _check(modified, path):
            if modified:
                modified = [line.split()[-1] for line in modified]
                raise ReleaseVCSError(
                    "%s is not in a state to release - please commit outstanding "
                    "changes: %s" % (path, ', '.join(modified)))

        _check(self.hg('status', '-m', '-a'), self.vcs_root)
        if self.patch_path:
            _check(self.hg('status', '-m', '-a', '--mq'), self.patch_path)

    def get_current_revision(self):
        doc = {
            'commit': self.hg("log", "--template", "{node}", "-r", ".")[0],
            'branch': self.hg("branch")[0],
        }

        def _get(key, fn):
            try:
                value = fn()
                doc[key] = value
                return (value is not None)
            except Exception as e:
                print_error("Error retrieving %s: %s" % (key, str(e)))
                return False

        _get("push_url", self.get_default_url)

        return doc

    def get_changelog(self, previous_revision=None, max_revisions=None):
        prev_commit = None
        if previous_revision is not None:
            try:
                prev_commit = previous_revision["commit"]
            except:
                if self.package.config.debug("package_release"):
                    print_debug("couldn't determine previous commit from: %r"
                                % previous_revision)

        args = ["log"]
        if max_revisions:
            args.extend(["-l", str(max_revisions)])
        if prev_commit:
            # git behavior is to simply print the log from the last common
            # ancsestor... which is apparently desired. so we'll mimic that

            # however, we want to print in order from most recent to oldest,
            # because:
            #    a) if the log gets truncated, we want to cut off the
            #       oldest commits, not the current one, and
            #    b) this mimics the order they're printed in git
            #    c) this mimics the order they're printed if  you have no
            #       previous_revision, and just do "hg log"
            #    d) if max_revisions is giving, want limiting will only take the
            #       most recent N entries
            commit_range = "reverse(ancestor(%s, .)::.)" % prev_commit
            args.extend(["-r", commit_range])

        stdout = self.hg(*args)
        return '\n'.join(stdout)

    def create_release_tag(self, tag_name, message=None):
        # check if tag already exists, and if it does, if it is a direct
        # ancestor, and there is NO difference in the files between the tagged
        # state and current state
        #
        # This check is mainly to avoid re-creating the same tag over and over
        # on what is essentially the same commit, since tagging will
        # technically create a new commit, and update the working copy to it.
        #
        # Without this check, say you were releasing to three different
        # locations, one right after another; the first would create the tag,
        # and a new tag commit.  The second would then recreate the exact same
        # tag, but now pointing at the commit that made the first tag.
        # The third would create the tag a THIRD time, but now pointing at the
        # commit that created the 2nd tag.

        # create tag
        print("Creating tag '%s'..." % tag_name)
        created_tags = self._create_tag_highlevel(tag_name, message=message)

        # push tags / bookmarks
        for result in created_tags:
            patch = result['patch']
            url = self.get_default_url(patch=patch)
            if not url:
                continue
            if result['type'] == 'bookmark':
                self.hg('push', '--bookmark', tag_name, url, patch=patch)
            elif result['type'] == 'tag':
                self.hg('push', url, patch=patch)
            else:
                raise ValueError(result['type'])


def register_plugin():
    return HgReleaseVCS


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
