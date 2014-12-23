"""
Filesystem-based package repository
"""
from rez.package_repository import PackageRepository
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    DerivedVariantResource, PackageResourceHelper, package_pod_schema
from rez.exceptions import PackageMetadataError
from rez.utils.formatting import is_valid_package_name, PackageRequest
from rez.utils.resources import cached_property
from rez.serialise import load_from_file, FileFormat
from rez.config import config
from rez.memcache import mem_cached, DataType
from rez.backport.lru_cache import lru_cache
import os.path
import os


#------------------------------------------------------------------------------
# utility functions
#------------------------------------------------------------------------------

def get_package_definition_file(path):
    for format_ in FileFormat:
        filename = "package.%s" % format_.extension
        filepath = os.path.join(path, filename)
        if os.path.isfile(filepath):
            return filepath, format_
    return None, None


#------------------------------------------------------------------------------
# resources
#------------------------------------------------------------------------------

class FileSystemPackageFamilyResource(PackageFamilyResource):
    key = "filesystem.family"
    repository_type = "filesystem"

    def _uri(self):
        return os.path.join(self.location, self.name)

    def get_last_release_time(self):
        # this repository makes sure to update path mtime every time a
        # variant is added to the repository [TODO: coming]
        path = os.path.join(self.location, self.name)
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    def iter_packages(self):
        root = self.uri

        # check for unversioned package
        filepath, _ = get_package_definition_file(root)
        if filepath:
            package = self._repository.get_resource(
                FileSystemPackageResource.key,
                location=self.location,
                name=self.name)
            yield package
            return

        # versioned packages
        for version_str in self._repository._get_version_dirs(root):
            package = self._repository.get_resource(
                FileSystemPackageResource.key,
                location=self.location,
                name=self.name,
                version=version_str)
            yield package


class FileSystemPackageResource(PackageResourceHelper):
    key = "filesystem.package"
    variant_key = "filesystem.variant"
    repository_type = "filesystem"
    schema = package_pod_schema

    def _uri(self):
        return self.filepath

    @property
    def base(self):
        return self._path()

    @cached_property
    def parent(self):
        family = self._repository.get_resource(
            FileSystemPackageFamilyResource.key,
            location=self.location,
            name=self.name)
        return family

    @cached_property
    def state_handle(self):
        if self.filepath:
            return os.path.getmtime(self.filepath)
        return None

    def _path(self):
        path = os.path.join(self.location, self.name)
        ver_str = self.get("version")
        if ver_str:
            path = os.path.join(path, ver_str)
        return path

    @cached_property
    def filepath(self):
        return self._filepath_and_format[0]

    @cached_property
    def file_format(self):
        return self._filepath_and_format[1]

    @cached_property
    def _filepath_and_format(self):
        path = self._path()
        return get_package_definition_file(path)

    def _load(self):
        if self.filepath is None:
            raise PackageMetadataError("Missing package definition file: %r" % self)

        data = load_from_file(self.filepath, self.file_format)

        if "timestamp" not in data:  # old format support
            data_ = self._load_old_formats()
            if data_:
                data.update(data_)

        return data

    def _load_old_formats(self):
        data = None
        path = self.uri

        filepath = os.path.join(path, "release.yaml")
        if os.path.isfile(filepath):
            # rez<2.0.BETA.16
            data = load_from_file(filepath, FileFormat.yaml,
                                  update_data_callback=self._update_changelog)
        else:
            path_ = os.path.join(path, ".metadata")
            if os.path.isdir(path_):
                # rez-1
                data = {}
                filepath = os.path.join(path_, "changelog.txt")
                if os.path.isfile(filepath):
                    data["changelog"] = load_from_file(
                        filepath, FileFormat.txt,
                        update_data_callback=self._update_changelog)

                filepath = os.path.join(path_, "release_time.txt")
                if os.path.isfile(filepath):
                    value = load_from_file(filepath, FileFormat.txt)
                    try:
                        data["timestamp"] = int(value.strip())
                    except:
                        pass
        return data

    def _update_changelog(self, file_format, data):
        # this is to deal with older package releases. They can contain long
        # changelogs (more recent rez versions truncate before release), and
        # release.yaml files can contain a list-of-str changelog.
        maxlen = config.max_package_changelog_chars

        if file_format == FileFormat.yaml:
            changelog = data.get("changelog")
            if changelog:
                changed = False
                if isinstance(changelog, list):
                    changelog = '\n'.join(changelog)
                    changed = True
                if len(changelog) > (maxlen + 3):
                    changelog = changelog[:maxlen] + "..."
                    changed = True
                if changed:
                    data["changelog"] = changelog
        else:
            assert isinstance(data, basestring)
            if len(data) > (maxlen + 3):
                data = data[:maxlen] + "..."

        return data


class FileSystemVariantResource(DerivedVariantResource):
    key = "filesystem.variant"
    repository_type = "filesystem"

    @cached_property
    def parent(self):
        package = self._repository.get_resource(
            FileSystemPackageResource.key,
            location=self.location,
             name=self.name,
             version=self.get("version"))
        return package


#------------------------------------------------------------------------------
# repository
#------------------------------------------------------------------------------

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

    def __init__(self, location, resource_pool):
        """Create a filesystem package repository.

        Args:
            location (str): Path containing the package repository.
        """
        super(FileSystemPackageRepository, self).__init__(location, resource_pool)
        self.register_resource(FileSystemPackageFamilyResource)
        self.register_resource(FileSystemPackageResource)
        self.register_resource(FileSystemVariantResource)

    def _uid(self):
        st = os.stat(self.location)
        return ("filesystem", self.location, st.st_ino)

    def get_package_family(self, name):
        return self._get_family(name)

    def iter_package_families(self):
        for family in self._get_families():
            yield family

    def iter_packages(self, package_family_resource):
        for package in self._get_packages(package_family_resource):
            yield package

    def iter_variants(self, package_resource):
        for variant in self._get_variants(package_resource):
            yield variant

    def get_parent_package_family(self, package_resource):
        return package_resource.parent

    def get_parent_package(self, variant_resource):
        return variant_resource.parent

    def get_variant_state_handle(self, variant_resource):
        package_resource = variant_resource.parent
        return package_resource.state_handle

    def get_last_release_time(self, package_family_resource):
        return package_family_resource.get_last_release_time()

    # -- internal

    def _get_family_dirs__key(self):
        st = os.stat(self.location)
        return (self.location, st.st_ino, st.st_mtime)

    @mem_cached(DataType.listdir, key_func=_get_family_dirs__key)
    def _get_family_dirs(self):
        dirs = []
        for name in os.listdir(self.location):
            path = os.path.join(self.location, name)
            if is_valid_package_name(name) and os.path.isdir(path):
                dirs.append(name)
        return dirs

    def _get_version_dirs__key(self, root):
        st = os.stat(root)
        return (root, st.st_ino, st.st_mtime)

    @mem_cached(DataType.listdir, key_func=_get_version_dirs__key)
    def _get_version_dirs(self, root):
        dirs = []
        for name in os.listdir(root):
            if name.startswith('.'):
                continue
            path = os.path.join(root, name)
            if os.path.isdir(path):
                dirs.append(name)
        return dirs

    @lru_cache(maxsize=None)
    def _get_families(self):
        families = []
        for name in self._get_family_dirs():
            family = self.get_resource(
                FileSystemPackageFamilyResource.key,
                location=self.location,
                name=name)
            families.append(family)
        return families

    @lru_cache(maxsize=None)
    def _get_family(self, name):
        is_valid_package_name(name, raise_error=True)
        if os.path.isdir(os.path.join(self.location, name)):
            family = self.get_resource(
                FileSystemPackageFamilyResource.key,
                location=self.location,
                name=name)
            return family
        return None

    @lru_cache(maxsize=None)
    def _get_packages(self, package_family_resource):
        return [x for x in package_family_resource.iter_packages()]

    @lru_cache(maxsize=None)
    def _get_variants(self, package_resource):
        return [x for x in package_resource.iter_variants()]


def register_plugin():
    return FileSystemPackageRepository
