import re
from rez.exceptions import ReleaseVCSError
from rezplugins.release_vcs.git import GitReleaseVCS


class GitHubReleaseVCSError(ReleaseVCSError):
    pass


class GitHubReleaseVCS(GitReleaseVCS):

    @classmethod
    def name(cls):
        return 'github'

    def validate_repostate(self):
        super(GitHubReleaseVCS, self).validate_repostate()

        # Check that the repository is not a fork and belongs to the white listed organizations
        current_organization = self._get_organization()
        releasable = False
        for organization in self.type_settings.releasable_organizations:
            if re.search(organization, current_organization):
                releasable = True

        if not releasable:
            raise GitHubReleaseVCSError("GitHub organization %s is not among the allowed organizations %s"
                                        % (current_organization, self.type_settings.releasable_organizations))

    def _get_remote_origin_url(self):
        return self.git('config', 'remote.origin.url')[0]

    def _get_organization(self):
        # Assumes we always have http://DOMAIN/ORG/REPO
        try:
            return self._get_remote_origin_url().split('/')[-2]
        except IndexError:
            return GitHubReleaseVCSError("Could not retrieve the GiHub organization from the origin remote: %s "
                                         % self._get_remote_origin_url())


def register_plugin():
    return GitHubReleaseVCS