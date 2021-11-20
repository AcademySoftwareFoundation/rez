# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Svn version control
"""
from __future__ import print_function

from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSError
import os.path
import pysvn

# TODO this needs a rewrite


class SvnReleaseVCSError(ReleaseVCSError):
    pass


def svn_get_client():
    # check we're in an svn working copy
    client = pysvn.Client()
    client.set_interactive(True)
    client.set_auth_cache(False)
    client.set_store_passwords(False)
    client.callback_get_login = get_svn_login
    return client


def get_last_changed_revision(client, url):
    """
    util func, get last revision of url
    """
    try:
        svn_entries = client.info2(url,
                                   pysvn.Revision(pysvn.opt_revision_kind.head),
                                   recurse=False)
        if not svn_entries:
            raise ReleaseVCSError("svn.info2() returned no results on url %s" % url)
        return svn_entries[0][1].last_changed_rev
    except pysvn.ClientError as ce:
        raise ReleaseVCSError("svn.info2() raised ClientError: %s" % ce)


def get_svn_login(realm, username, may_save):
    """
    provide svn with permissions. @TODO this will have to be updated to take
    into account automated releases etc.
    """
    import getpass

    print("svn requires a password for the user %s:" % username)
    pwd = ''
    while not pwd.strip():
        pwd = getpass.getpass("--> ")

    return True, username, pwd, False


class SvnReleaseVCS(ReleaseVCS):
    @classmethod
    def name(cls):
        return 'svn'

    def __init__(self, pkg_root, vcs_root=None):
        super(SvnReleaseVCS, self).__init__(pkg_root, vcs_root=vcs_root)

        self.svnc = svn_get_client()
        svn_entry = self.svnc.info(self.pkg_root)
        if not svn_entry:
            raise SvnReleaseVCSError("%s is not an svn working copy"
                                     % self.pkg_root)
        self.this_url = str(svn_entry["url"])

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isdir(os.path.join(path, '.svn'))

    @classmethod
    def search_parents_for_root(cls):
        return True

    def validate_repostate(self):
        status_list = self.svnc.status(self.pkg_root, get_all=False, update=True)
        status_list_known = []

        for status in status_list:
            if status.entry:
                status_list_known.append(status)

        if status_list_known:
            raise ReleaseVCSError(
                "'%s' is not in a state to release - you may need to svn-checkin "
                "and/or svn-update: %s" % (self.pkg_root, str(status_list_known)))

    def _create_tag_impl(self, tag_name, message=None):
        tag_url = self.get_tag_url(tag_name)
        print("rez-release: creating project tag in: %s..." % tag_url)
        self.svnc.callback_get_log_message = lambda x: (True, x)
        self.svnc.copy2([(self.this_url,)], tag_url, make_parents=True)

    def get_changelog(self, previous_revision=None, max_revisions=None):
        return "TODO"

    def get_tag_url(self, tag_name=None):
        # find the base path, ie where 'trunk', 'branches', 'tags' should be
        pos_tr = self.this_url.find("/trunk")
        pos_br = self.this_url.find("/branches")
        pos = max(pos_tr, pos_br)
        if (pos == -1):
            raise ReleaseVCSError("%s is not in a branch or trunk" % self.pkg_root)
        base_url = self.this_url[:pos]
        tag_url = base_url + "/tags"

        if tag_name:
            tag_url += '/' + tag_name
        return tag_url

    def svn_url_exists(self, url):
        try:
            svnlist = self.svnc.info2(url, recurse=False)
            return bool(svnlist)
        except pysvn.ClientError:
            return False

    def get_current_revision(self):
        return self.svnc.info(self.pkg_root)['revision'].number

    def create_release_tag(self, tag_name, message=None):
        # svn requires a message - if not provided, make it the same as the
        # tag name..
        if not message:
            message = tag_name
        self.svnc.callback_get_log_message = lambda: (True, message)
        self.svnc.copy(self.pkg_root, self.get_tag_url(tag_name))


def register_plugin():
    return SvnReleaseVCS
