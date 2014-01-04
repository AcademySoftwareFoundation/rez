from rez.util import encode_filesystem_name, movetree, is_pkg_dir
from rez.source_retrieval import get_source
import os.path



class FormulaeManager(object):
    """
    Manages formulae repositories used by rez-install, and installs packages
    from these formulae.
    """
    def __init__(self):
        # TODO control via settings
        self.repo_urls = ["https://github.com/LumaPictures/rez-build/archive/master.zip"]
        #self.repo_urls = ["git@github.com:LumaPictures/rez-build.git"]
        self.repos = dict((x,{}) for x in self.repo_urls)

    def get_urls(self):
        """ @returns A list of urls that formula repos are downloaded from """
        return self.repo_urls

    def get_packages(self, url):
        """ @returns A list of packages (as strings) contained in the given repo """
        repo = self._get_repo(url)
        if "pkgs" not in repo:
            pkgs = []
            repo_dir = self._get_repo_dir(url)
            if os.path.exists(repo_dir):
                for pkg_name in os.listdir(repo_dir):
                    dir_ = os.path.join(repo_dir, pkg_name)
                    if is_pkg_dir(dir_):
                        pkgs.append(pkg_name)
                    else:
                        for pkg_ver in os.listdir(dir_):
                            if is_pkg_dir(os.path.join(dir_, pkg_ver)):
                                pkg = "%s-%s" % (pkg_name, pkg_ver)
                                pkgs.append(pkg)

            repo["pkgs"] = pkgs

        return repo["pkgs"]

    def update_repository(self, url):
        """
        Update a formulae repository
        @returns List of newly added packages.
        """
        # TODO get from settings
        cache_path = os.path.expanduser('~/.rez/downloads/formulae-repos')

        old_pkgs = self.get_packages(url)
        dest_path = self._get_repo_dir(url)
        dl_path = get_source(url, dest_path, cache_path=cache_path)

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
        # TODO use settings
        repos_dir = os.path.expanduser("~/.rez/formulae-repos")
        dirname = encode_filesystem_name(url)
        return os.path.join(repos_dir, dirname)


# singleton
formulae_manager = FormulaeManager()
