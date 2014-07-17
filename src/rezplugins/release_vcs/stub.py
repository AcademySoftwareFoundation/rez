"""
Stub version control system, for testing purposes
"""
from rez.release_vcs import ReleaseVCS
import os.path
import time


class StubReleaseVCS(ReleaseVCS):
    """A release VCS that doesn't really do anything. Used by unit tests.
    """
    def __init__(self, path):
        super(StubReleaseVCS, self).__init__(path)
        self.time = int(time.time())

    @classmethod
    def name(cls):
        return "stub"

    @classmethod
    def is_valid_root(cls, path):
        return os.path.exists(os.path.join(path, '.stub'))

    def validate_repostate(self):
        pass

    def get_current_revision(self):
        return self.time

    def get_changelog(self, previous_revision=None):
        if previous_revision:
            if isinstance(previous_revision, int):
                seconds = self.time - previous_revision
                return ["This commit was %d seconds after the last" % seconds]
            else:
                return ["There is a previous commit from a different vcs"]
        else:
            return ["This is the first commit"]

    def create_release_tag(self, tag_name, message=None):
        print "Creating tag '%s'..." % tag_name
        pass


def register_plugin():
    return StubReleaseVCS
