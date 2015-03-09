import commands
from rez.config import Str
from rez.exceptions import ReleaseVCSError
from rezplugins.release_vcs.git import GitReleaseVCS
from rez import config


class GitHubReleaseVCSError(ReleaseVCSError):
    pass


class GitHubReleaseVCS(GitReleaseVCS):

    @classmethod
    def name(cls):
        return 'github'


    def validate_repostate(self):
        # Check that the repository is not a fork and belongs to the white listed organizations
        super(GitHubReleaseVCS, self).validate_repostate()
        org = self._get_organization()
        if org not in self.type_settings.releasable_organizations:
            raise GitHubReleaseVCSError("GitHub organization %s not among the allowed organizations %s"
                                        % (org, self.type_settings.releasable_organizations))

    def _get_remote_origin_url(self):
        return self.git('config', 'remote.origin.url')

    def _get_organization(self):
        # Assume we always have http://DOMAIN/ORG/REPO
        try:
            return self._get_remote_origin_url().split('/')[-2]
        except IndexError:
            return GitHubReleaseVCSError("Could not retrieve the GiHub organization from the origin remote: %s "
                                         % self._get_remote_origin_url())

    def _get_remote_origin_domain_name(self):
        # Assume we always have http://DOMAIN/ORG/REPO
        try:
            return self._get_remote_origin_url().split('/')[2]
        except IndexError:
            return GitHubReleaseVCSError("Could not retrieve the GiHub origin remote domain name from: %s "
                                         % self._get_remote_origin_url())


def register_plugin():
    return GitHubReleaseVCS