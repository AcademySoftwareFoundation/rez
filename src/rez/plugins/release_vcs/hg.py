from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
from rez import plugin_factory
import subprocess
import os.path



executable = ReleaseVCS.find_executable('hg')


def hg(*args):
    """
    call the `hg` executable with the list of arguments provided.
    Return a list of output lines if the call is successful, else raise RezReleaseError
    """
    cmd = [executable] + list(args)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode:
        # TODO: create a new error type and add the error string to an attribute
        raise ReleaseVCSError("failed to call: hg " + ' '.join(args) + '\n' + err)
    out = out.rstrip('\n')
    if not out:
        return []
    return out.split('\n')


class HgReleaseVCS(ReleaseVCS):
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
            assert hg('root')[0] == self.path
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

    def _create_tag_impl(self, tag_name, message=None):
        if self.patch_path:
            # patch queue
            hg('tag', '-f', tag_name, '--message', message, '--mq')
            # use a bookmark on the main repo since we can't change it
            hg('bookmark', '-f', tag_name)
        else:
            hg('tag', '-f', tag_name)

    def validate_repostate(self):
        def _check(modified, path):
            if modified:
                modified = [line.split()[-1] for line in modified]
                raise ReleaseVCSError(("%s is not in a state to release - please " + \
                    "commit outstanding changes: %s") % (path, ', '.join(modified)))

        _check(hg('status', '-m', '-a'), self.path)
        if self.patch_path:
            _check(hg('status', '-m', '-a', '--mq'), self.patch_path)

    def get_changelog(self, previous_revision=None):
        return "TODO"



class HgReleaseVCSFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return HgReleaseVCS
