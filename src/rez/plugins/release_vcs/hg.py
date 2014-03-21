from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
from rez import plugin_factory
import os.path



class HgReleaseVCS(ReleaseVCS):
    executable = ReleaseVCS.find_executable('hg')

    @classmethod
    def name(cls):
        return 'hg'

    def __init__(self, path):
        super(HgReleaseVCS, self).__init__(path)

        hgdir = os.path.join(self.path, '.hg')
        if not os.path.isdir(hgdir):
            raise ReleaseVCSUnsupportedError( \
                "'%s' is not a mercurial working copy" % self.path)
        try:
            assert self.hg('root')[0] == self.path
        except AssertionError:
            raise ReleaseVCSUnsupportedError( \
                "'%s' is not the root of a mercurial working copy" % self.path)
        except Exception, err:
            raise ReleaseVCSUnsupportedError("failed to call hg binary: " + str(err))

        self.patch_path = os.path.join(hgdir, 'patches')
        if not os.path.isdir(self.patch_path):
            self.patch_path = None

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isdir(os.path.join(path, '.hg'))

    def hg(self, *nargs):
        return self._cmd(self.executable, *nargs)

    def _create_tag_impl(self, tag_name, message=None):
        if self.patch_path:
            # patch queue
            self.hg('tag', '-f', tag_name, '--message', message, '--mq')
            # use a bookmark on the main repo since we can't change it
            self.hg('bookmark', '-f', tag_name)
        else:
            self.hg('tag', '-f', tag_name)

    def validate_repostate(self):
        def _check(modified, path):
            if modified:
                modified = [line.split()[-1] for line in modified]
                raise ReleaseVCSError(("%s is not in a state to release - please " + \
                    "commit outstanding changes: %s") % (path, ', '.join(modified)))

        _check(self.hg('status', '-m', '-a'), self.path)
        if self.patch_path:
            _check(self.hg('status', '-m', '-a', '--mq'), self.patch_path)

    def get_changelog(self, previous_revision=None):
        return "TODO"



class HgReleaseVCSFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return HgReleaseVCS
