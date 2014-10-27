"""
Stub version control system, for testing purposes
"""
from rez.release_vcs import ReleaseVCS
from rez.util import print_warning
from rez.vendor import yaml
from rez.yaml import dump_yaml
import os.path
import time


class StubReleaseVCS(ReleaseVCS):
    """A release VCS that doesn't really do anything. Used by unit tests.

    A writable '.stub' file must be present in the project root. Any created
    tags are written to this yaml file.
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
                return "This commit was %d seconds after the last" % seconds
            else:
                return "There is a previous commit from a different vcs"
        else:
            return "This is the first commit"

    def create_release_tag(self, tag_name, message=None):
        data = self._read_stub()
        if "tags" not in data:
            data["tags"] = {}
        elif tag_name in data["tags"]:
            print_warning("Skipped tag creation, tag '%s' already exists" % tag_name)
            return

        print "Creating tag '%s'..." % tag_name
        data["tags"][tag_name] = message
        self._write_stub(data)

    def _read_stub(self):
        with open(os.path.join(self.path, '.stub')) as f:
            return yaml.load(f.read()) or {}

    def _write_stub(self, data):
        with open(os.path.join(self.path, '.stub'), 'w') as f:
            f.write(dump_yaml(data))


def register_plugin():
    return StubReleaseVCS
