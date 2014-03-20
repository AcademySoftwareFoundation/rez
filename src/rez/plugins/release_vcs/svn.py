from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
from rez import plugin_factory
import subprocess
import os.path
import pysvn



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
    except pysvn.ClientError, ce:
        raise ReleaseVCSError("svn.info2() raised ClientError: %s" % ce)

def get_svn_login(realm, username, may_save):
    """
    provide svn with permissions. @TODO this will have to be updated to take
    into account automated releases etc.
    """
    import getpass

    print "svn requires a password for the user %s:" % username
    pwd = ''
    while not pwd.strip():
        pwd = getpass.getpass("--> ")

    return True, username, pwd, False



class SvnReleaseVCS(ReleaseVCS):
    @classmethod
    def name(cls):
        return 'svn'

    def __init__(self, path):
        super(GitReleaseVCS, self).__init__(path)

        self.svnc = svn_get_client()
        svn_entry = self.svnc.info(self.path)
        if not svn_entry:
            raise ReleaseVCSUnsupportedError("%s is not an svn working copy"
                                             % self.path)
        self.this_url = str(svn_entry["url"])

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isdir(os.path.join(path, '.svn'))

    def validate_repostate(self):
        status_list = self.svnc.status(self.path, get_all=False, update=True)
        status_list_known = []

        for status in status_list:
            if status.entry:
                status_list_known.append(status)

        if status_list_known:
            raise ReleaseVCSError("'" + self.path + "' is not in a state to " + \
                "release - you may need to svn-checkin and/or svn-update: " + \
                str(status_list_known))

    def _create_tag_impl(self, tag_name, message=None):
        tag_url = self.get_tag_url(tag_name)
        print "rez-release: creating project tag in: %s..." % tag_url
        self.svnc.callback_get_log_message = lambda x:(True,x)
        self.svnc.copy2([(self.this_url,)], tag_url, make_parents=True)

    def get_changelog(self, previous_revision=None):
        return "TODO"

    def get_tag_url(self, tag_name=None):
        # find the base path, ie where 'trunk', 'branches', 'tags' should be
        pos_tr = self.this_url.find("/trunk")
        pos_br = self.this_url.find("/branches")
        pos = max(pos_tr, pos_br)
        if (pos == -1):
            raise ReleaseVCSError("%s is not in a branch or trunk" % self.path)
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



class SvnReleaseVCSFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return SvnReleaseVCS
