"""
Filesystem-based package repository
"""
from rez.package_repository import PackageRepository
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResourceHelper, PackageResourceHelper, package_pod_schema, \
    package_release_keys, package_build_only_keys
from rez.serialise import clear_file_caches, open_file_for_write
from rez.package_serialise import dump_package_data
from rez.exceptions import PackageMetadataError, ResourceError, RezSystemError, \
    ConfigurationError, PackageRepositoryError
from rez.utils.formatting import is_valid_package_name, PackageRequest
from rez.utils.resources import cached_property
from rez.serialise import load_from_file, FileFormat
from rez.config import config
from rez.utils.memcached import memcached, pool_memcached_connections
from rez.backport.lru_cache import lru_cache
from rez.vendor.schema.schema import Schema, Optional, And, Use, Or
from rez.vendor.version.version import Version, VersionRange
import time
import os.path
import os


#------------------------------------------------------------------------------
# utilities
#------------------------------------------------------------------------------


# this is set when the package repository is instantiated, otherwise an infinite
# loop is caused to to config loading this plugin, loading config ad infinitum
_settings = None


class PackageDefinitionFileMissing(PackageMetadataError):
    pass


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
        # variant is added to the repository
        path = os.path.join(self.location, self.name)
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    def iter_packages(self):
        # check for unversioned package
        if config.allow_unversioned_packages:
            filepath, _ = self._repository._get_file(self.path)
            if filepath:
                package = self._repository.get_resource(
                    FileSystemPackageResource.key,
                    location=self.location,
                    name=self.name)
                yield package
                return

        # versioned packages
        for version_str in self._repository._get_version_dirs(self.path):
            if _settings.check_package_definition_files:
                path = os.path.join(self.path, version_str)
                if not self._repository._get_file(path)[0]:
                    continue

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
        return self._repository._get_file(self.path)

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

    @staticmethod
    def _update_changelog(file_format, data):
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
        if config.allow_unversioned_packages and not self.versions:
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
    schema_dict = {"file_lock_timeout": int,
                   "file_lock_dir": Or(None, str),
                   "package_filenames": [basestring]}

    building_prefix = ".building"

    @classmethod
    def name(cls):
        return "filesystem"

    def __init__(self, location, resource_pool):
        """Create a filesystem package repository.

        Args:
            location (str): Path containing the package repository.
        """
        super(FileSystemPackageRepository, self).__init__(location, resource_pool)

        global _settings
        _settings = config.plugins.package_repository.filesystem

        self.register_resource(FileSystemPackageFamilyResource)
        self.register_resource(FileSystemPackageResource)
        self.register_resource(FileSystemVariantResource)

        self.register_resource(FileSystemCombinedPackageFamilyResource)
        self.register_resource(FileSystemCombinedPackageResource)
        self.register_resource(FileSystemCombinedVariantResource)

        self.get_families = lru_cache(maxsize=None)(self._get_families)
        self.get_family = lru_cache(maxsize=None)(self._get_family)
        self.get_packages = lru_cache(maxsize=None)(self._get_packages)
        self.get_variants = lru_cache(maxsize=None)(self._get_variants)
        self.get_file = lru_cache(maxsize=None)(self._get_file)

    def _uid(self):
        t = ["filesystem", self.location]
        if os.path.exists(self.location):
            st = os.stat(self.location)
            t.append(st.st_ino)
        return tuple(t)

    def get_package_family(self, name):
        return self.get_family(name)

    @pool_memcached_connections
    def iter_package_families(self):
        for family in self.get_families():
            yield family

    @pool_memcached_connections
    def iter_packages(self, package_family_resource):
        for package in self.get_packages(package_family_resource):
            yield package

    def iter_variants(self, package_resource):
        for variant in self.get_variants(package_resource):
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

    @cached_property
    def file_lock_dir(self):
        dirname = _settings.file_lock_dir
        if not dirname:
            return None

        # sanity check
        if os.path.isabs(dirname) or os.path.basename(dirname) != dirname:
            raise ConfigurationError(
                "filesystem package repository setting 'file_lock_dir' must be "
                "a single relative directory such as '.lock'")

        # fall back to location path if lock dir doesn't exist.
        path = os.path.join(self.location, dirname)
        if not os.path.exists(path):
            return None

        return dirname

    def pre_variant_install(self, variant_resource):
        if not variant_resource.version:
            return

        # create 'building' tagfile, this makes sure that a resolve doesn't
        # pick up this package if it doesn't yet have a package.py created.
        path = self.location

        family_path = os.path.join(path, variant_resource.name)
        if not os.path.isdir(family_path):
            os.makedirs(family_path)

        filename = self.building_prefix + str(variant_resource.version)
        filepath = os.path.join(family_path, filename)

        with open(filepath, 'w'):  # create empty file
            pass

    def install_variant(self, variant_resource, dry_run=False, overrides=None):
        if variant_resource._repository is self:
            return variant_resource

        from rez.vendor.lockfile import LockFile
        filename = ".lock.%s" % variant_resource.name
        if variant_resource.version:
            filename += "-%s" % str(variant_resource.version)

        path = self.location
        if self.file_lock_dir:
            path = os.path.join(path, self.file_lock_dir)

        if not os.path.exists(path):
            raise PackageRepositoryError(
                "Lockfile directory %s does not exist - please create and try "
                "again" % path)

        lock_file = os.path.join(path, filename)
        lock = LockFile(lock_file)

        try:
            lock.acquire(timeout=_settings.file_lock_timeout)
            variant = self._create_variant(variant_resource, dry_run=dry_run,
                                           overrides=overrides)
        finally:
            if lock.is_locked():
                lock.release()

        return variant

    def clear_caches(self):
        super(FileSystemPackageRepository, self).clear_caches()
        self.get_families.cache_clear()
        self.get_family.cache_clear()
        self.get_packages.cache_clear()
        self.get_variants.cache_clear()
        self.get_file.cache_clear()
        self._get_family_dirs.forget()
        self._get_version_dirs.forget()
        # unfortunately we need to clear file cache across the board
        clear_file_caches()

    # -- internal

    def _get_family_dirs__key(self):
        if os.path.isdir(self.location):
            st = os.stat(self.location)
            return str(("listdir", self.location, st.st_ino, st.st_mtime))
        else:
            return str(("listdir", self.location))

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
                if is_valid_package_name(name) and name != self.file_lock_dir:
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

        # simpler case if this test is on
        #
        if _settings.check_package_definition_files:
            dirs = []

            for name in os.listdir(root):
                if name.startswith('.'):
                    continue

                path = os.path.join(root, name)
                if os.path.isdir(path):
                    if not self._is_valid_package_directory(path):
                        continue

                dirs.append(name)
            return dirs

        # with test off, we have to check for 'building' dirs, these have to be
        # tested regardless. Failed releases may cause 'building files' to be
        # left behind, so we need to clear these out also
        #
        dirs = set()
        building_dirs = set()

        # find dirs and dirs marked as 'building'
        for name in os.listdir(root):
            if name.startswith('.'):
                if not name.startswith(self.building_prefix):
                    continue

                ver_str = name[len(self.building_prefix):]
                building_dirs.add(ver_str)

            path = os.path.join(root, name)
            if os.path.isdir(path):
                dirs.add(name)

        # check 'building' dirs for validity
        for name in building_dirs:
            if name not in dirs:
                continue

            path = os.path.join(root, name)
            if not self._is_valid_package_directory(path):
                # package probably still being built
                dirs.remove(name)

        return list(dirs)

    # True if `path` contains package.py or similar
    def _is_valid_package_directory(self, path):
        return bool(self._get_file(path, "package")[0])

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

    def _get_family(self, name):
        is_valid_package_name(name, raise_error=True)
        if os.path.isdir(os.path.join(self.location, name)):
            family = self.get_resource(
                FileSystemPackageFamilyResource.key,
                location=self.location,
                name=name)
            return family
        else:
            filepath, format_ = self.get_file(self.location, package_filename=name)
            if filepath:
                family = self.get_resource(
                    FileSystemCombinedPackageFamilyResource.key,
                    location=self.location,
                    name=name,
                    ext=format_.extension)
                return family
        return None

    def _get_packages(self, package_family_resource):
        return [x for x in package_family_resource.iter_packages()]

    def _get_variants(self, package_resource):
        return [x for x in package_resource.iter_variants()]

    def _get_file(self, path, package_filename=None):
        if package_filename:
            package_filenames = [package_filename]
        else:
            package_filenames = _settings.package_filenames

        for name in package_filenames:
            for format_ in (FileFormat.py, FileFormat.yaml):
                filename = "%s.%s" % (name, format_.extension)
                filepath = os.path.join(path, filename)
                if os.path.isfile(filepath):
                    return filepath, format_
        return None, None

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

        def remove_build_keys(obj):
            for key in package_build_only_keys:
                obj.pop(key, None)

        remove_build_keys(new_package_data)

        if existing_package:
            existing_package_data = existing_package.validated_data()
            remove_build_keys(existing_package_data)

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
            variant_requires = variant.variant_requires

            for variant_ in self.iter_variants(existing_package):
                variant_requires_ = existing_package.variants[variant_.index]
                if variant_requires_ == variant_requires:
                    installed_variant_index = variant_.index
                    if dry_run and not package_changed:
                        return variant_
                    break

            parent_package = existing_package

            _, file_  = os.path.split(existing_package.filepath)
            package_filename, package_extension = os.path.splitext(file_)
            package_extension = package_extension[1:]
            package_format = FileFormat[package_extension]

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
            package_filename = _settings.package_filenames[0]
            package_extension = "py"
            package_format = FileFormat.py

        if dry_run:
            return None

        # merge existing release data (if any) into the package. Note that when
        # this data becomes variant-specific, this step will no longer be needed
        package_data.update(release_data)

        # merge the new variant into the package
        if installed_variant_index is None and variant.index is not None:
            variant_requires = variant.variant_requires
            if not package_data.get("variants"):
                package_data["variants"] = []
            package_data["variants"].append(variant_requires)
            installed_variant_index = len(package_data["variants"]) - 1

        # a little data massaging is needed
        package_data["config"] = parent_package._data.get("config")
        package_data.pop("base", None)

        # create version dir if it doesn't already exist
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

        package_file = ".".join([package_filename, package_extension])
        filepath = os.path.join(path, package_file)

        with open_file_for_write(filepath) as f:
            dump_package_data(package_data, buf=f, format_=package_format)

        # delete the tmp 'building' file.
        if variant.version:
            filename = self.building_prefix + str(variant.version)
            filepath = os.path.join(family_path, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

        # delete other stale building files; previous failed releases may have
        # left some around
        try:
            self._delete_stale_build_tagfiles(family_path)
        except:
            pass

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

    def _delete_stale_build_tagfiles(self, family_path):
        now = time.time()

        for name in os.listdir(family_path):
            if not name.startswith(self.building_prefix):
                continue

            tagfilepath = os.path.join(family_path, name)
            ver_str = name[len(self.building_prefix):]
            pkg_path = os.path.join(family_path, ver_str)

            if os.path.exists(pkg_path):
                # build tagfile not needed if package is valid
                if self._is_valid_package_directory(pkg_path):
                    os.remove(tagfilepath)
                    continue
            else:
                # remove tagfile if pkg is gone. Delete only tagfiles over a certain
                # age, otherwise might delete a tagfile another process has created
                # just before it created the package directory.
                st = os.stat(tagfilepath)
                age = now - st.st_mtime

                if age > 3600:
                    os.remove(tagfilepath)


def register_plugin():
    return FileSystemPackageRepository


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
