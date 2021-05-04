"""
Filesystem-based package repository
"""
from contextlib import contextmanager
import os.path
import os
import stat
import errno
import time
import shutil

from rez.package_repository import PackageRepository
from rez.package_resources import PackageFamilyResource, VariantResourceHelper, \
    PackageResourceHelper, package_pod_schema, \
    package_release_keys, package_build_only_keys
from rez.serialise import clear_file_caches, open_file_for_write, load_from_file, \
    FileFormat
from rez.package_serialise import dump_package_data
from rez.exceptions import PackageMetadataError, ResourceError, RezSystemError, \
    ConfigurationError, PackageRepositoryError
from rez.utils.resources import ResourcePool
from rez.utils.formatting import is_valid_package_name
from rez.utils.resources import cached_property
from rez.utils.logging_ import print_warning, print_info
from rez.utils.memcached import memcached, pool_memcached_connections
from rez.utils.filesystem import make_path_writable, \
    canonical_path, is_subdirectory
from rez.utils.platform_ import platform_
from rez.utils.yaml import load_yaml
from rez.config import config
from rez.backport.lru_cache import lru_cache
from rez.vendor.schema.schema import Schema, Optional, And, Use, Or
from rez.vendor.six import six
from rez.vendor.version.version import Version, VersionRange


basestring = six.string_types[0]


debug_print = config.debug_printer("resources")


# ------------------------------------------------------------------------------
# format version
#
# 1:
# Initial format.
# 2:
# Late binding functions added.
# ------------------------------------------------------------------------------
format_version = 2


def check_format_version(filename, data):
    format_version_ = data.pop("format_version", None)

    if format_version_ is not None:
        try:
            format_version_ = int(format_version_)
        except:
            return

        if format_version_ > format_version:
            print_warning(
                "Loading from %s may fail: newer format version (%d) than current "
                "format version (%d)" % (filename, format_version_, format_version))


# ------------------------------------------------------------------------------
# utilities
# ------------------------------------------------------------------------------


# this is set when the package repository is instantiated, otherwise an infinite
# loop is caused to to config loading this plugin, loading config ad infinitum
_settings = None


class PackageDefinitionFileMissing(PackageMetadataError):
    pass


# ------------------------------------------------------------------------------
# resources
# ------------------------------------------------------------------------------

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
        try:
            return os.path.getmtime(self.path)
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
        # Note: '_redirected_base' is a special attribute set by the build
        # process in order to perform pre-install/release package testing. See
        # `LocalBuildProcess._run_tests()`
        #
        redirected_base = self._data.get("_redirected_base")

        return redirected_base or self.path

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

        data = load_from_file(
            self.filepath,
            self.file_format,
            disable_memcache=self._repository.disable_memcache
        )

        check_format_version(self.filepath, data)

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
        Optional("versions"): [
            And(basestring, Use(Version))
        ],
        Optional("version_overrides"): {
            And(basestring, Use(VersionRange)): dict
        }
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
        data = load_from_file(
            self.filepath,
            format_,
            disable_memcache=self._repository.disable_memcache
        )

        check_format_version(self.filepath, data)
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
                for range_, data_ in overrides.items():
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


# ------------------------------------------------------------------------------
# repository
# ------------------------------------------------------------------------------

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
                   "file_lock_type": Or("default", "link", "mkdir"),
                   "package_filenames": [basestring]}

    building_prefix = ".building"
    ignore_prefix = ".ignore"

    package_file_mode = (
        None if os.name == "nt" else

        # These aren't supported on Windows
        # https://docs.python.org/2/library/os.html#os.chmod
        (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    )

    @classmethod
    def name(cls):
        return "filesystem"

    def __init__(self, location, resource_pool):
        """Create a filesystem package repository.

        Args:
            location (str): Path containing the package repository.
        """

        # ensure that differing case doesn't get interpreted as different repos
        # on case-insensitive platforms (eg windows)
        location = canonical_path(location, platform_)

        super(FileSystemPackageRepository, self).__init__(location, resource_pool)

        # load settings optionally defined in a settings.yaml
        local_settings = {}
        settings_filepath = os.path.join(location, "settings.yaml")
        if os.path.exists(settings_filepath):
            local_settings.update(load_yaml(settings_filepath))

        self.disable_memcache = local_settings.get("disable_memcache", False)

        # TODO allow these settings to be overridden in settings.yaml also
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

        # decorate with memcachemed memoizers unless told otherwise
        if not self.disable_memcache:
            decorator1 = memcached(
                servers=config.memcached_uri if config.cache_listdir else None,
                min_compress_len=config.memcached_listdir_min_compress_len,
                key=self._get_family_dirs__key,
                debug=config.debug_memcache
            )
            self._get_family_dirs = decorator1(self._get_family_dirs)

            decorator2 = memcached(
                servers=config.memcached_uri if config.cache_listdir else None,
                min_compress_len=config.memcached_listdir_min_compress_len,
                key=self._get_version_dirs__key,
                debug=config.debug_memcache
            )
            self._get_version_dirs = decorator2(self._get_version_dirs)

        self._disable_pkg_ignore = False

    def _uid(self):
        t = ["filesystem", self.location]
        if os.path.exists(self.location):
            st = os.stat(self.location)
            t.append(int(st.st_ino))
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

    def get_package_from_uri(self, uri):
        """
        Example URIs:
        - /svr/packages/mypkg/1.0.0/package.py
        - /svr/packages/mypkg/package.py  # (unversioned package - rare)
        - /svr/packages/mypkg/package.py<1.0.0>  # ("combined" package type - rare)
        """
        uri = os.path.normcase(uri)

        prefix = self.location + os.path.sep
        if not is_subdirectory(uri, prefix):
            return None

        part = uri[len(prefix):]  # eg 'mypkg/1.0.0/package.py'
        parts = part.split(os.path.sep)
        pkg_name = parts[0]

        if len(parts) == 2:
            if '<' in part:
                # "combined" package type, like 'mypkg/package.py<1.0.0>'
                pkg_ver_str = parts[1][1:-1]
            else:
                # 'mypkg/package.py' (unversioned)
                pkg_ver_str = ''
        elif len(parts) == 3:
            # typical case: 'mypkg/1.0.0/package.py'
            pkg_ver_str = parts[1]
        else:
            return None

        # find package
        pkg_ver = Version(pkg_ver_str)
        return self.get_package(pkg_name, pkg_ver)

    def get_variant_from_uri(self, uri):
        """
        Example URIs:
        - /svr/packages/mypkg/1.0.0/package.py[1]
        - /svr/packages/mypkg/1.0.0/package.py[]  # ("null" variant)
        - /svr/packages/mypkg/package.py[1]  # (unversioned package - rare)
        - /svr/packages/mypkg/package.py<1.0.0>[1]  # ("combined" package type - rare)
        """
        i = uri.rfind('[')
        if i == -1:
            return None

        package_uri = uri[:i]  # eg 'mypkg/1.0.0/package.py'
        variant_index_str = uri[i + 1:-1]  # the '1' in '[1]'

        # find package
        pkg = self.get_package_from_uri(package_uri)
        if pkg is None:
            return None

        # find variant in package
        if variant_index_str == '':
            variant_index = None
        else:
            try:
                variant_index = int(variant_index_str)
            except ValueError:
                # future proof - we may move to hash-based indices for hashed variants
                variant_index = variant_index_str

        for variant in pkg.iter_variants():
            if variant.index == variant_index:
                return variant

        return None

    def ignore_package(self, pkg_name, pkg_version, allow_missing=False):
        # find package, even if already ignored
        if not allow_missing:
            repo_copy = self._copy(disable_pkg_ignore=True)
            if not repo_copy.get_package(pkg_name, pkg_version):
                return -1

        filename = self.ignore_prefix + str(pkg_version)
        fam_path = os.path.join(self.location, pkg_name)
        filepath = os.path.join(fam_path, filename)

        # do nothing if already ignored
        if os.path.exists(filepath):
            return 0

        # create .ignore{ver} file
        try:
            os.makedirs(fam_path)
        except OSError:  # already exists
            pass

        with open(filepath, 'w'):
            pass

        self._on_changed(pkg_name)
        return 1

    def unignore_package(self, pkg_name, pkg_version):
        # find and remove .ignore{ver} file if it exists
        ignore_file_was_removed = False
        filename = self.ignore_prefix + str(pkg_version)
        filepath = os.path.join(self.location, pkg_name, filename)

        if os.path.exists(filepath):
            os.remove(filepath)
            ignore_file_was_removed = True

        if self.get_package(pkg_name, pkg_version):
            if ignore_file_was_removed:
                self._on_changed(pkg_name)
                return 1
            else:
                return 0
        else:
            return -1

    def remove_package(self, pkg_name, pkg_version):
        # ignore it first, so a partially deleted pkg is not visible
        i = self.ignore_package(pkg_name, pkg_version)
        if i == -1:
            return False

        # check for combined-style package, this is not supported
        repo_copy = self._copy(disable_pkg_ignore=True)

        pkg = repo_copy.get_package(pkg_name, pkg_version)
        assert pkg

        if isinstance(pkg, FileSystemCombinedPackageResource):
            raise NotImplementedError(
                "Package removal not supported in combined-style packages")

        # delete the payload
        pkg_dir = os.path.join(self.location, pkg_name, str(pkg_version))
        shutil.rmtree(pkg_dir)

        # unignore (just so the .ignore{ver} file is removed)
        self.unignore_package(pkg_name, pkg_version)

        return True

    def remove_ignored_since(self, days, dry_run=False, verbose=False):
        now = int(time.time())
        num_removed = 0

        def _info(msg, *nargs):
            if verbose:
                print_info(msg, *nargs)

        for fam in self._get_families():
            fam_path = os.path.join(self.location, fam.name)
            if not os.path.isdir(fam_path):
                continue  # might be a combined-style package

            for name in os.listdir(fam_path):
                if not name.startswith(self.ignore_prefix):
                    continue

                # get age of .ignore{ver} file
                filepath = os.path.join(fam_path, name)
                st = os.stat(filepath)
                age_secs = now - int(st.st_ctime)
                age_days = age_secs / (3600 * 24)

                if age_days < days:
                    continue

                # extract pkg version from .ignore filename
                ver_str = name[len(self.ignore_prefix):]

                # remove the package
                if dry_run:
                    _info("Would remove %s-%s from %s", fam.name, ver_str, self)
                    num_removed += 1

                elif self.remove_package(fam.name, Version(ver_str)):
                    num_removed += 1
                    _info("Removed %s-%s from %s", fam.name, ver_str, self)

        return num_removed

    def get_resource_from_handle(self, resource_handle, verify_repo=True):
        if verify_repo:
            repository_type = resource_handle.variables.get("repository_type")
            location = resource_handle.variables.get("location")

            if repository_type != self.name():
                raise ResourceError("repository_type mismatch - requested %r, "
                                    "repository_type is %r"
                                    % (repository_type, self.name()))

            # It appears that sometimes, the handle location can differ to the
            # repo location even though they are the same path (different
            # mounts). We account for that here.
            #
            # https://github.com/nerdvegas/rez/pull/957
            #
            if location != self.location:
                location = canonical_path(location, platform_)

            if location != self.location:
                raise ResourceError("location mismatch - requested %r, "
                                    "repository location is %r "
                                    % (location, self.location))

        resource = self.pool.get_resource_from_handle(resource_handle)
        resource._repository = self
        return resource

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

    def on_variant_install_cancelled(self, variant_resource):
        """
        TODO:
            Currently this will not delete a newly created package version
            directory. The reason is because behaviour with multiple rez procs
            installing variants of the same package in parallel is not well
            tested and hasn't been fully designed for yet. Currently, if this
            did delete the version directory, it could delete it while another
            proc is performing a successful variant install into the same dir.

            Note though that this does do useful work, if the cancelled variant
            was getting installed into an existing package. In this case, the
            .building file is deleted, because the existing package.py is valid.

            Work has to be done to change the way that new variant dirs and the
            .building file are created, so that we can safely delete cancelled
            variant dirs in the presence of multiple rez procs.

            See https://github.com/nerdvegas/rez/issues/810
        """
        family_path = os.path.join(self.location, variant_resource.name)
        self._delete_stale_build_tagfiles(family_path)

    def install_variant(self, variant_resource, dry_run=False, overrides=None):
        overrides = overrides or {}

        # Name and version overrides are a special case - they change the
        # destination variant to be created/replaced.
        #
        variant_name = variant_resource.name
        variant_version = variant_resource.version

        if "name" in overrides:
            variant_name = overrides["name"]
            if variant_name is self.remove:
                raise PackageRepositoryError(
                    "Cannot remove package attribute 'name'")

        if "version" in overrides:
            ver = overrides["version"]
            if ver is self.remove:
                raise PackageRepositoryError(
                    "Cannot remove package attribute 'version'")

            if isinstance(ver, basestring):
                ver = Version(ver)
                overrides = overrides.copy()
                overrides["version"] = ver

            variant_version = ver

        # cannot install over one's self, just return existing variant
        if variant_resource._repository is self and \
                variant_name == variant_resource.name and \
                variant_version == variant_resource.version:
            return variant_resource

        # create repo path on disk if it doesn't exist
        path = self.location

        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise PackageRepositoryError(
                    "Package repository path %r could not be created: %s: %s"
                    % (path, e.__class__.__name__, e)
                )

        # install the variant
        def _create_variant():
            return self._create_variant(
                variant_resource,
                dry_run=dry_run,
                overrides=overrides
            )

        if dry_run:
            variant = _create_variant()
        else:
            with self._lock_package(variant_name, variant_version):
                variant = _create_variant()

        return variant

    def _copy(self, disable_pkg_ignore=False):
        """
        Make a copy of the repo that does not share resources with this one.
        """
        pool = ResourcePool(cache_size=None)
        repo_copy = self.__class__(self.location, pool)

        if disable_pkg_ignore:
            repo_copy._disable_pkg_ignore = True

        return repo_copy

    @contextmanager
    def _lock_package(self, package_name, package_version=None):
        from rez.vendor.lockfile import NotLocked

        if _settings.file_lock_type == 'default':
            from rez.vendor.lockfile import LockFile
        elif _settings.file_lock_type == 'mkdir':
            from rez.vendor.lockfile.mkdirlockfile import MkdirLockFile as LockFile
        elif _settings.file_lock_type == 'link':
            from rez.vendor.lockfile.linklockfile import LinkLockFile as LockFile

        path = self.location

        if self.file_lock_dir:
            path = os.path.join(path, self.file_lock_dir)

        if not os.path.exists(path):
            raise PackageRepositoryError(
                "Lockfile directory %s does not exist - please create and try "
                "again" % path)

        filename = ".lock.%s" % package_name
        if package_version:
            filename += "-%s" % str(package_version)

        lock_file = os.path.join(path, filename)
        lock = LockFile(lock_file)

        try:
            lock.acquire(timeout=_settings.file_lock_timeout)
            yield

        finally:
            try:
                lock.release()
            except NotLocked:
                pass

    def clear_caches(self):
        super(FileSystemPackageRepository, self).clear_caches()
        self.get_families.cache_clear()
        self.get_family.cache_clear()
        self.get_packages.cache_clear()
        self.get_variants.cache_clear()
        self.get_file.cache_clear()

        if not self.disable_memcache:
            self._get_family_dirs.forget()
            self._get_version_dirs.forget()

        # unfortunately we need to clear file cache across the board
        clear_file_caches()

    def get_package_payload_path(self, package_name, package_version=None):
        path = os.path.join(self.location, package_name)

        if package_version:
            path = os.path.join(path, str(package_version))

        return path

    # -- internal

    def _get_family_dirs__key(self):
        if os.path.isdir(self.location):
            st = os.stat(self.location)
            return str(("listdir", self.location, int(st.st_ino), st.st_mtime))
        else:
            return str(("listdir", self.location))

    def _get_family_dirs(self):
        dirs = []
        if not os.path.isdir(self.location):
            return dirs

        for name in os.listdir(self.location):
            path = os.path.join(self.location, name)

            if name in ("settings.yaml", self.file_lock_dir):
                continue  # skip reserved file/dirnames

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
        return str(("listdir", root, int(st.st_ino), st.st_mtime))

    def _get_version_dirs(self, root):
        # Ignore a version if there is a .ignore<version> file next to it
        def ignore_dir(name):
            if self._disable_pkg_ignore:
                return False
            else:
                path = os.path.join(root, self.ignore_prefix + name)
                return os.path.isfile(path)

        # simpler case if this test is on
        #
        if _settings.check_package_definition_files:
            dirs = []

            for name in os.listdir(root):
                if name.startswith('.'):
                    continue

                path = os.path.join(root, name)

                if os.path.isdir(path) and not ignore_dir(name) \
                        and self._is_valid_package_directory(path):
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

            if os.path.isdir(path) and not ignore_dir(name):
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
            # force case-sensitive match on pkg family dir, on case-insensitive platforms
            if not platform_.has_case_sensitive_filesystem and \
                    name not in os.listdir(self.location):
                return None

            return self.get_resource(
                FileSystemPackageFamilyResource.key,
                location=self.location,
                name=name
            )
        else:
            filepath, format_ = self.get_file(self.location, package_filename=name)
            if filepath:
                # force case-sensitive match on pkg filename, on case-insensitive platforms
                if not platform_.has_case_sensitive_filesystem:
                    ext = os.path.splitext(filepath)[-1]
                    if (name + ext) not in os.listdir(self.location):
                        return None

                return self.get_resource(
                    FileSystemCombinedPackageFamilyResource.key,
                    location=self.location,
                    name=name,
                    ext=format_.extension
                )
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

        self._on_changed(name)
        return self.get_package_family(name)

    def _create_variant(self, variant, dry_run=False, overrides=None):
        # special case overrides
        variant_name = overrides.get("name") or variant.name
        variant_version = overrides.get("version") or variant.version

        overrides = (overrides or {}).copy()
        overrides.pop("name", None)
        overrides.pop("version", None)

        # find or create the package family
        family = self.get_package_family(variant_name)
        if not family:
            family = self._create_family(variant_name)

        if isinstance(family, FileSystemCombinedPackageFamilyResource):
            raise NotImplementedError(
                "Cannot install variant into combined-style package file %r."
                % family.filepath)

        # find the package if it already exists
        existing_package = None

        for package in self.iter_packages(family):
            if package.version == variant_version:
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

        existing_package_data = None
        release_data = {}

        # Need to treat 'config' as special case. In validated data, this is
        # converted to a Config object. We need it as the raw dict that you'd
        # see in a package.py.
        #
        def _get_package_data(pkg):
            data = pkg.validated_data()
            if hasattr(pkg, "_data"):
                raw_data = pkg._data
            else:
                raw_data = pkg.resource._data

            raw_config_data = raw_data.get('config')
            data.pop("config", None)

            if raw_config_data:
                data["config"] = raw_config_data

            return data

        def _remove_build_keys(obj):
            for key in package_build_only_keys:
                obj.pop(key, None)

        new_package_data = _get_package_data(variant.parent)
        new_package_data.pop("variants", None)
        new_package_data["name"] = variant_name
        if variant_version:
            new_package_data["version"] = variant_version
        package_changed = False

        _remove_build_keys(new_package_data)

        if existing_package:
            debug_print(
                "Found existing package for installation of variant %s: %s",
                variant.uri, existing_package.uri
            )

            existing_package_data = _get_package_data(existing_package)
            _remove_build_keys(existing_package_data)

            # detect case where new variant introduces package changes outside of variant
            data_1 = existing_package_data.copy()
            data_2 = new_package_data.copy()

            for key in package_release_keys:
                data_2.pop(key, None)
                value = data_1.pop(key, None)
                if value is not None:
                    release_data[key] = value

            for key in ("format_version", "base", "variants"):
                data_1.pop(key, None)
                data_2.pop(key, None)

            package_changed = (data_1 != data_2)

            if debug_print:
                if package_changed:
                    from rez.utils.data_utils import get_dict_diff_str

                    debug_print("Variant %s package data differs from package %s",
                                variant.uri, existing_package.uri)

                    txt = get_dict_diff_str(data_1, data_2, "Changes:")
                    debug_print(txt)
                else:
                    debug_print("Variant %s package data matches package %s",
                                variant.uri, existing_package.uri)

        # check for existing installed variant
        existing_installed_variant = None
        installed_variant_index = None

        if existing_package:
            if variant.index is None:
                existing_installed_variant = \
                    next(self.iter_variants(existing_package))
            else:
                variant_requires = variant.variant_requires

                for variant_ in self.iter_variants(existing_package):
                    variant_requires_ = existing_package.variants[variant_.index]
                    if variant_requires_ == variant_requires:
                        installed_variant_index = variant_.index
                        existing_installed_variant = variant_

        if existing_installed_variant:
            debug_print(
                "Variant %s already has installed equivalent: %s",
                variant.uri, existing_installed_variant.uri
            )

        if dry_run:
            if not package_changed:
                return existing_installed_variant
            else:
                return None

        # construct package data for new installed package definition
        if existing_package:
            _, file_ = os.path.split(existing_package.filepath)
            package_filename, package_extension = os.path.splitext(file_)
            package_extension = package_extension[1:]
            package_format = FileFormat[package_extension]

            if package_changed:
                # graft together new package data, with existing package variants,
                # and other data that needs to stay unchanged (eg timestamp)
                package_data = new_package_data

                if variant.index is not None:
                    package_data["variants"] = existing_package_data.get("variants", [])
            else:
                package_data = existing_package_data
        else:
            package_data = new_package_data
            package_filename = _settings.package_filenames[0]
            package_extension = "py"
            package_format = FileFormat.py

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
        package_data.pop("base", None)

        # create version dir if it doesn't already exist
        family_path = os.path.join(self.location, variant_name)
        if variant_version:
            pkg_base_path = os.path.join(family_path, str(variant_version))
        else:
            pkg_base_path = family_path
        if not os.path.exists(pkg_base_path):
            os.makedirs(pkg_base_path)

        # Apply overrides.
        #
        # If we're installing into an existing package, then existing attributes
        # in that package take precedence over `overrides`. If we're installing
        # to a new package, then `overrides` takes precedence always.
        #
        # This is done so that variants added to an existing package don't change
        # attributes such as 'timestamp' or release-related fields like 'revision'.
        #
        for key, value in overrides.items():
            if existing_package:
                if key not in package_data:
                    package_data[key] = value
            else:
                if value is self.remove:
                    package_data.pop(key, None)
                else:
                    package_data[key] = value

        # timestamp defaults to now if not specified
        if not package_data.get("timestamp"):
            package_data["timestamp"] = int(time.time())

        # format version is always set
        package_data["format_version"] = format_version

        # Stop if package is unversioned and config does not allow that
        if not package_data["version"] and not config.allow_unversioned_packages:
            raise PackageMetadataError("Unversioned package is not allowed "
                                       "in current configuration.")

        # write out new package definition file
        package_file = ".".join([package_filename, package_extension])
        filepath = os.path.join(pkg_base_path, package_file)

        with make_path_writable(pkg_base_path):
            with open_file_for_write(filepath, mode=self.package_file_mode) as f:
                dump_package_data(package_data, buf=f, format_=package_format)

        # delete the tmp 'building' file.
        if variant_version:
            filename = self.building_prefix + str(variant_version)
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

        self._on_changed(variant_name)

        # load new variant. Note that we load it from a copy of this repo, with
        # package ignore disabled. We do this so it's possible to install
        # variants into a hidden (ignored) package. This is used by `move_package`
        # in order to make the moved package visible only after all its variants
        # have been copied over.
        #
        new_variant = None

        repo_copy = self._copy(disable_pkg_ignore=True)
        pkg = repo_copy.get_package(variant_name, variant_version)

        if pkg is not None:
            for variant_ in self.iter_variants(pkg):
                if variant_.index == installed_variant_index:
                    new_variant = variant_
                    break

        if not new_variant:
            raise RezSystemError("Internal failure - expected installed variant")

        # a bit hacky but it works. We need the variant to belong to the actual
        # repo, not the temp copy we retrieved it from
        #
        new_variant._repository = self

        return new_variant

    def _on_changed(self, pkg_name):
        """Called when a package is added/removed/changed.
        """

        # update access time of family dir. This is done so that very few file
        # stats are required to determine if a resolve cache entry is stale.
        #
        family_path = os.path.join(self.location, pkg_name)
        os.utime(family_path, None)

        # clear internal caches, otherwise change may not be visible
        self.clear_caches()

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
