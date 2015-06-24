"""
Mercurial version control
"""
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
        except Exception, err:
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
        if kwargs:
            raise HgReleaseVCSError("Unrecognized keyword args to hg command:"
                                    " %s" % ", ".join(kwargs))
        return self._cmd(self.executable, *nargs)

    def _create_tag_impl(self, tag_name, message=None):
        tag_args = ['tag', '-f', tag_name]
        if message:
            tag_args += ['--message', message]
        if self.patch_path:
            # patch queue
            self.hg(patch=True, *tag_args)
            # use a bookmark on the main repo since we can't change it
            self.hg('bookmark', '-f', tag_name)
        else:
            self.hg(*tag_args)

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

    def get_changelog(self, previous_revision=None):
        prev_commit = None
        if previous_revision is not None:
            try:
                prev_commit = previous_revision["commit"]
            except:
                if self.package.config.debug("package_release"):
                    print_debug("couldn't determine previous commit from: %r"
                                % previous_revision)

        if prev_commit:
            # git behavior is to simply print the log from the last common
            # ancsestor... which is apparently desired. so we'll mimic that
            commit_range = "ancestor(%s, .)::." % prev_commit
            stdout = self.hg("log", "-r", commit_range)
        else:
            stdout = self.hg("log")
        return '\n'.join(stdout)

    def create_release_tag(self, tag_name, message=None):
        # create tag
        print "Creating tag '%s'..." % tag_name
        self._create_tag_impl(tag_name, message=message)

        # push tag
        main_url = self.get_default_url()
        if self.patch_path:
            # push the tag on the patch repo...
            patch_url = self.get_default_url(patch=True)
            if patch_url:
                self.hg('push', patch_url, patch=True)

            # ...and push the bookmark on the main
            if main_url:
                self.hg('push', '--bookmark', tag_name, main_url)
        elif main_url:
            self.hg('push', main_url)


def register_plugin():
    return HgReleaseVCS
