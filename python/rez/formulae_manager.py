from rez.util import encode_filesystem_name, movetree
from rez.packages import iter_package_families, iter_packages_in_range
from rez.source_retrieval import get_source
from rez.settings import settings
import os.path



class FormulaeManager(object):
    """
    Manages formulae repositories used by rez-install, and installs packages
    from these formulae.
    """
    def __init__(self):
        self.repo_urls = settings.package_repository_url_path
        self.repos = dict((x,{}) for x in self.repo_urls)

    def get_urls(self):
        """ @returns A list of urls that formula repos are downloaded from """
        return self.repo_urls

    def get_packages(self, url):
        """ @returns A list of packages (as strings) contained in the given repo """
        # TODO port to resources
        repo = self._get_repo(url)
        if "pkgs" not in repo:
            pkgs = []
            repo_dir = self._get_repo_dir(url)
            if os.path.exists(repo_dir):
                for pkg_fam in iter_package_families(paths=[repo_dir]):
                    for pkg in iter_packages_in_range(pkg_fam.name, paths=[repo_dir]):
                        pkgs.append(pkg.short_name())
            repo["pkgs"] = pkgs

        return repo["pkgs"]

    def update_repository(self, url):
        """
        Update a formulae repository
        @returns List of newly added packages.
        """
        old_pkgs = self.get_packages(url)
        dest_path = self._get_repo_dir(url)
        dl_path = get_source(url, dest_path,
                             cache_path=settings.package_repository_cache_path)

        if dl_path != dest_path:
            print "Moving %s..." % dl_path
            movetree(dl_path, dest_path)

        repo = self._get_repo(url)
        if "pkgs" in repo:
            del repo["pkgs"]
        new_pkgs = self.get_packages(url)
        return sorted(list(set(new_pkgs) - set(old_pkgs)))

    def install_package(self, url, pkg, dry_run=False):
        print "Installing %s..." % pkg

    def _get_repo(self, url):
        repo = self.repos.get(url)
        if repo is None:
            raise RuntimeError("Unregistered formulae url: %s" % url)
        return repo

    @classmethod
    def _get_repo_dir(cls, url):
        dirname = encode_filesystem_name(url)
        return os.path.join(settings.package_repository_path, dirname)


# singleton
formulae_manager = FormulaeManager()
