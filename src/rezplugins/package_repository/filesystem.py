"""
Filesystem-based package repository
"""
from rez.package_repository import PackageRepository


class FileSystemPackageRepository(PackageRepository):
    """A filesystem-based package repository.

    Packages are stored on disk, in either 'package.yaml' or 'package.py' files.
    These files are stored into an organised directory structure like so:

        /LOCATION/pkgA/1.0.0/package.py
                      /1.0.1/package.py
                 /pkgB/2.1/package.py
                      /2.2/package.py
    """
    @classmethod
    def name(cls):
        return "filesystem"

    def __init__(self, location):
        """Create a filesystem package repository.

        Args:
            location (str): Path containing the package repository.
        """
        super(FileSystemPackageRepository, self).__init__()


def register_plugin():
    return FileSystemPackageRepository
