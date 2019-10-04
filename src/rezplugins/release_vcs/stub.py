"""
Stub version control system, for testing purposes
"""
from __future__ import print_function

from rez.release_vcs import ReleaseVCS
from rez.utils.logging_ import print_warning
from rez.utils.yaml import dump_yaml
from rez.vendor import yaml
import os.path
import time


class StubReleaseVCS(ReleaseVCS):
    """A release VCS that doesn't really do anything. Used by unit tests.

    A writable '.stub' file must be present in the project root. Any created
    tags are written to this yaml file.
    """
    def __init__(self, pkg_root, vcs_root=None):
        super(StubReleaseVCS, self).__init__(pkg_root, vcs_root=vcs_root)
        self.time = int(time.time())

    @classmethod
    def name(cls):
        return "stub"

    @classmethod
    def is_valid_root(cls, path):
        return os.path.exists(os.path.join(path, '.stub'))

    @classmethod
    def search_parents_for_root(cls):
        return False

    def validate_repostate(self):
        pass

    def get_current_revision(self):
        return self.time

    def get_changelog(self, previous_revision=None, max_revisions=None):
        if previous_revision:
            if isinstance(previous_revision, int):
                seconds = self.time - previous_revision
                return "This commit was %d seconds after the last" % seconds
            else:
                return "There is a previous commit from a different vcs"
        else:
            return "This is the first commit"

    def tag_exists(self, tag_name):
        data = self._read_stub()
        return tag_name in data.get("tags", [])

    def create_release_tag(self, tag_name, message=None):
        data = self._read_stub()
        if "tags" not in data:
            data["tags"] = {}
        elif tag_name in data["tags"]:
            print_warning("Skipped tag creation, tag '%s' already exists" % tag_name)
            return

        print("Creating tag '%s'..." % tag_name)
        data["tags"][tag_name] = message
        self._write_stub(data)

    def _read_stub(self):
        with open(os.path.join(self.vcs_root, '.stub')) as f:
            return yaml.load(f.read(), Loader=yaml.FullLoader) or {}

    def _write_stub(self, data):
        with open(os.path.join(self.vcs_root, '.stub'), 'w') as f:
            f.write(dump_yaml(data))


def register_plugin():
    return StubReleaseVCS


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
