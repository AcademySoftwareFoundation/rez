"""
Filesystem-based package repository
"""
from rez.package_repository import PackageRepository
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResourceHelper, PackageResourceHelper, package_pod_schema, \
    package_release_keys
from rez.serialise import clear_file_caches
from rez.package_serialise import dump_package_data
from rez.exceptions import PackageMetadataError, ResourceError, RezSystemError
from rez.utils.formatting import is_valid_package_name, PackageRequest
from rez.utils.resources import cached_property
from rez.serialise import load_from_file, FileFormat
from rez.config import config
from rez.utils.memcached import memcached
from rez.backport.lru_cache import lru_cache
from rez.vendor.schema.schema import Schema, Optional, And, Use
from rez.vendor.version.version import Version, VersionRange
import time
import os.path
import os


#------------------------------------------------------------------------------
# utilities
#------------------------------------------------------------------------------

class PackageDefinitionFileMissing(PackageMetadataError):
    pass


# get a file that could be .yaml or .py
def _get_file(path, name):
    for format_ in (FileFormat.py, FileFormat.yaml):
        filename = "%s.%s" % (name, format_.extension)
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
        return self.path

    @cached_property
    def path(self):
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
        # check for unversioned package
        filepath, _ = _get_file(self.path, "package")
        if filepath:
            package = self._repository.get_resource(
                FileSystemPackageResource.key,
                location=self.location,
                name=self.name)
            yield package
            return

        # versioned packages
        for version_str in self._repository._get_version_dirs(self.path):
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

    @property
    def base(self):
        return self.path

    @cached_property
    def path(self):
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
        return _get_file(self.path, "package")

    def _load(self):
        if self.filepath is None:
            raise PackageDefinitionFileMissing(
                "Missing package definition file: %r" % self)

        data = load_from_file(self.filepath, self.file_format)

        if "timestamp" not in data:  # old format support
            data_ = self._load_old_formats()
            if data_:
                data.update(data_)

        return data

    def _load_old_formats(self):
        data = None

        filepath = os.path.join(self.path, "release.yaml")
        if os.path.isfile(filepath):
            # rez<2.0.BETA.16
            data = load_from_file(filepath, FileFormat.yaml,
                                  update_data_callback=self._update_changelog)
        else:
            path_ = os.path.join(self.path, ".metadata")
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
        if not maxlen:
            return data

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


class FileSystemVariantResource(VariantResourceHelper):
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


# -- 'combined' resource types

class FileSystemCombinedPackageFamilyResource(PackageFamilyResource):
    key = "filesystem.family.combined"
    repository_type = "filesystem"

    schema = Schema({
        Optional("versions"):               [And(basestring,
                                                 Use(Version))],
        Optional("version_overrides"):      {And(basestring,
                                                 Use(VersionRange)): dict}
    })

    @property
    def ext(self):
        return self.get("ext")

    @property
    def filepath(self):
        filename = "%s.%s" % (self.name, self.ext)
        return os.path.join(self.location, filename)

    def _uri(self):
        return self.filepath

    def get_last_release_time(self):
        try:
            return os.path.getmtime(self.filepath)
        except OSError:
            return 0

    def iter_packages(self):
        # unversioned package
        if not self.versions:
            package = self._repository.get_resource(
                FileSystemCombinedPackageResource.key,
                location=self.location,
                name=self.name,
                ext=self.ext)
            yield package
            return

        # versioned packages
        for version in self.versions:
            package = self._repository.get_resource(
                FileSystemCombinedPackageResource.key,
                location=self.location,
                name=self.name,
                ext=self.ext,
                version=str(version))
            yield package

    def _load(self):
        format_ = FileFormat[self.ext]
        data = load_from_file(self.filepath, format_)
        return data


class FileSystemCombinedPackageResource(PackageResourceHelper):
    key = "filesystem.package.combined"
    variant_key = "filesystem.variant.combined"
    repository_type = "filesystem"
    schema = package_pod_schema

    def _uri(self):
        ver_str = self.get("version", "")
        return "%s<%s>" % (self.parent.filepath, ver_str)

    @cached_property
    def parent(self):
        family = self._repository.get_resource(
            FileSystemCombinedPackageFamilyResource.key,
            location=self.location,
            name=self.name,
            ext=self.get("ext"))
        return family

    @property
    def base(self):
        return None  # combined resource types do not have 'base'

    @cached_property
    def state_handle(self):
        return os.path.getmtime(self.parent.filepath)

    def iter_variants(self):
        num_variants = len(self._data.get("variants", []))
        if num_variants == 0:
            indexes = [None]
        else:
            indexes = range(num_variants)

        for index in indexes:
            variant = self._repository.get_resource(
                self.variant_key,
                location=self.location,
                name=self.name,
                ext=self.get("ext"),
                version=self.get("version"),
                index=index)
            yield variant

    def _load(self):
        data = self.parent._data.copy()

        if "versions" in data:
            del data["versions"]
            version_str = self.get("version")
            data["version"] = version_str
            version = Version(version_str)

            overrides = self.parent.version_overrides
            if overrides:
                for range_, data_ in overrides.iteritems():
                    if version in range_:
                        data.update(data_)
                del data["version_overrides"]

        return data


class FileSystemCombinedVariantResource(VariantResourceHelper):
    key = "filesystem.variant.combined"
    repository_type = "filesystem"

    @cached_property
    def parent(self):
        package = self._repository.get_resource(
            FileSystemCombinedPackageResource.key,
            location=self.location,
            name=self.name,
            ext=self.get("ext"),
            version=self.get("version"))
        return package

    def _root(self):
        return None  # combined resource types do not have 'root'


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

    Another supported storage format is to store all package versions within a
    single package family in one file, like so:

        /LOCATION/pkgC.yaml
        /LOCATION/pkgD.py

    These 'combined' package files allow for differences between package
    versions via a 'package_overrides' section:

        name: pkgC

        versions:
        - '1.0'
        - '1.1'
        - '1.2'

        version_overrides:
            '1.0':
                requires:
                - python-2.5
            '1.1+':
                requires:
                - python-2.6
    """
    schema_dict = {"file_lock_timeout": int}

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

        self.register_resource(FileSystemCombinedPackageFamilyResource)
        self.register_resource(FileSystemCombinedPackageResource)
        self.register_resource(FileSystemCombinedVariantResource)

        self.settings = config.plugins.package_repository.filesystem

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

    def install_variant(self, variant_resource, dry_run=False, overrides=None):
        if variant_resource._repository is self:
            return variant_resource

        from rez.vendor.lockfile import LockFile
        filename = ".lock.%s" % variant_resource.name
        if variant_resource.version:
            filename += "-%s" % str(variant_resource.version)
        lock_file = os.path.join(self.location, filename)
        lock = LockFile(lock_file)

        try:
            lock.acquire(timeout=self.settings.file_lock_timeout)
            variant = self._create_variant(variant_resource, dry_run=dry_run,
                                           overrides=overrides)
        finally:
            if lock.is_locked():
                lock.release()

        return variant

    def clear_caches(self):
        super(FileSystemPackageRepository, self).clear_caches()
        self._get_families.cache_clear()
        self._get_family.cache_clear()
        self._get_packages.cache_clear()
        self._get_variants.cache_clear()
        self._get_family_dirs.forget()
        self._get_version_dirs.forget()
        # unfortunately we need to clear file cache across the board
        clear_file_caches()

    # -- internal

    def _get_family_dirs__key(self):
        st = os.stat(self.location)
        return str(("listdir", self.location, st.st_ino, st.st_mtime))

    @memcached(servers=config.memcached_uri if config.cache_listdir else None,
               min_compress_len=config.memcached_listdir_min_compress_len,
               key=_get_family_dirs__key,
               debug=config.debug_memcache)
    def _get_family_dirs(self):
        dirs = []
        if not os.path.isdir(self.location):
            return dirs
        for name in os.listdir(self.location):
            path = os.path.join(self.location, name)
            if os.path.isdir(path):
                if is_valid_package_name(name):
                    dirs.append((name, None))
            else:
                name_, ext_ = os.path.splitext(name)
                if ext_ in (".py", ".yaml") and is_valid_package_name(name_):
                    dirs.append((name_, ext_[1:]))
        return dirs

    def _get_version_dirs__key(self, root):
        st = os.stat(root)
        return str(("listdir", root, st.st_ino, st.st_mtime))

    @memcached(servers=config.memcached_uri if config.cache_listdir else None,
               min_compress_len=config.memcached_listdir_min_compress_len,
               key=_get_version_dirs__key,
               debug=config.debug_memcache)
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
        for name, ext in self._get_family_dirs():
            if ext is None:  # is a directory
                family = self.get_resource(
                    FileSystemPackageFamilyResource.key,
                    location=self.location,
                    name=name)
            else:
                family = self.get_resource(
                    FileSystemCombinedPackageFamilyResource.key,
                    location=self.location,
                    name=name,
                    ext=ext)
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
        else:
            filepath, format_ = _get_file(self.location, name)
            if filepath:
                family = self.get_resource(
                    FileSystemCombinedPackageFamilyResource.key,
                    location=self.location,
                    name=name,
                    ext=format_.extension)
                return family
        return None

    @lru_cache(maxsize=None)
    def _get_packages(self, package_family_resource):
        return [x for x in package_family_resource.iter_packages()]

    @lru_cache(maxsize=None)
    def _get_variants(self, package_resource):
        return [x for x in package_resource.iter_variants()]

    def _create_family(self, name):
        path = os.path.join(self.location, name)
        if not os.path.exists(path):
            os.makedirs(path)
        self.clear_caches()
        return self.get_package_family(name)

    def _create_variant(self, variant, dry_run=False, overrides=None):
        # find or create the package family
        family = self.get_package_family(variant.name)
        if not family:
            family = self._create_family(variant.name)

        if isinstance(family, FileSystemCombinedPackageFamilyResource):
            raise NotImplementedError(
                "Cannot install variant into combined-style package file %r."
                % family.filepath)

        # find the package if it already exists
        existing_package = None

        for package in self.iter_packages(family):
            if package.version == variant.version:
                # during a build, the family/version dirs get created ahead of
                # time, which causes a 'missing package definition file' error.
                # This is fine, we can just ignore it and write the new file.
                try:
                    package.validate_data()
                except PackageDefinitionFileMissing:
                    break

                uuids = set([variant.uuid, package.uuid])
                if len(uuids) > 1 and None not in uuids:
                    raise ResourceError(
                        "Cannot install variant %r into package %r - the "
                        "packages are not the same (UUID mismatch)"
                        % (variant, package))

                existing_package = package

                if variant.index is None:
                    if package.variants:
                        raise ResourceError(
                            "Attempting to install a package without variants "
                            "(%r) into an existing package with variants (%r)"
                            % (variant, package))
                elif not package.variants:
                    raise ResourceError(
                        "Attempting to install a variant (%r) into an existing "
                        "package without variants (%r)" % (variant, package))

        installed_variant_index = None
        existing_package_data = None
        existing_variants_data = None
        release_data = {}
        new_package_data = variant.parent.validated_data()
        new_package_data.pop("variants", None)
        package_changed = False

        if existing_package:
            existing_package_data = existing_package.validated_data()

            # detect case where new variant introduces package changes outside of variant
            data_1 = existing_package_data.copy()
            data_2 = new_package_data.copy()

            for key in package_release_keys:
                data_2.pop(key, None)
                value = data_1.pop(key, None)
                if value is not None:
                    release_data[key] = value

            for key in ("base", "variants"):
                data_1.pop(key, None)
                data_2.pop(key, None)
            package_changed = (data_1 != data_2)

        # special case - installing a no-variant pkg into a no-variant pkg
        if existing_package and variant.index is None:
            if dry_run and not package_changed:
                variant_ = self.iter_variants(existing_package).next()
                return variant_
            else:
                # just replace the package
                existing_package = None

        if existing_package:
            # see if variant already exists in package
            variant_requires = variant.parent.variants[variant.index]

            for variant_ in self.iter_variants(existing_package):
                variant_requires_ = existing_package.variants[variant_.index]
                if variant_requires_ == variant_requires:
                    installed_variant_index = variant_.index
                    if dry_run and not package_changed:
                        return variant_
                    break

            parent_package = existing_package
            ext = os.path.splitext(existing_package.filepath)[-1][1:]
            package_format = FileFormat[ext]

            if package_changed:
                # graft together new package data, with existing package variants,
                # and other data that needs to stay unchanged (eg timestamp)
                package_data = new_package_data
                package_data["variants"] = existing_package_data.get("variants", [])
            else:
                package_data = existing_package_data
        else:
            parent_package = variant.parent
            package_data = new_package_data
            package_format = FileFormat.py

        if dry_run:
            return None

        # merge existing release data (if any) into the package. Note that when
        # this data becomes variant-specific, this step will no longer be needed
        package_data.update(release_data)

        # merge the new variant into the package
        if installed_variant_index is None and variant.index is not None:
            variant_requires = variant.parent.variants[variant.index]
            if not package_data.get("variants"):
                package_data["variants"] = []
            package_data["variants"].append(variant_requires)
            installed_variant_index = len(package_data["variants"]) - 1

        # a little data massaging is needed
        package_data["config"] = parent_package._data.get("config")
        package_data.pop("base", None)

        # create version dir and write out the new package definition file
        family_path = os.path.join(self.location, variant.name)
        if variant.version:
            path = os.path.join(family_path, str(variant.version))
        else:
            path = family_path
        if not os.path.exists(path):
            os.makedirs(path)

        # add the timestamp
        overrides = overrides or {}
        overrides["timestamp"] = int(time.time())

        # apply attribute overrides
        for key, value in overrides.iteritems():
            if package_data.get(key) is None:
                package_data[key] = value

        filepath = os.path.join(path, "package.py")
        with open(filepath, 'w') as f:
            dump_package_data(package_data, buf=f, format_=package_format)

        # touch the family dir, this keeps memcached resolves updated properly
        os.utime(family_path, None)

        # load new variant
        new_variant = None
        self.clear_caches()
        family = self.get_package_family(variant.name)
        if family:
            for package in self.iter_packages(family):
                if package.version == variant.version:
                    for variant_ in self.iter_variants(package):
                        if variant_.index == installed_variant_index:
                            new_variant = variant_
                            break
                elif new_variant:
                    break

        if not new_variant:
            raise RezSystemError("Internal failure - expected installed variant")
        return new_variant


def register_plugin():
    return FileSystemPackageRepository
