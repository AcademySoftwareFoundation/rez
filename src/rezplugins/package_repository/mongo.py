from rez.vendor.version.requirement import VersionedObject
from rez.package_repository import PackageRepository
from rez.package_serialise import package_serialise_schema
from rez.package_resources_ import PackageFamilyResource, VariantResourceHelper,\
    PackageResourceHelper, package_pod_schema, package_release_keys
from rez.exceptions import PackageMetadataError, ResourceError, RezSystemError
from rez.utils.formatting import is_valid_package_name
from rez.utils.resources import cached_property
from rez.config import config
from rez.backport.lru_cache import lru_cache
import datetime
import time
import os.path
import os

from pymongo import MongoClient


class PackageDefinitionFileMissing(PackageMetadataError):
    pass

#------------------------------------------------------------------------------
# resources
#------------------------------------------------------------------------------


name_only = {'_id': 0, 'payload': 0, 'date': 0, 'payload.data': 0}
name_versions = {'_id': 0, 'date': 0, 'payload.data': 0}
name_date = {'_id': 0, 'payload': 0}
name_versions_date = {'_id': 0, 'payload.data': 0}
name_versions_date_data = {'_id': 0}


class MongoPackageFamilyResource(PackageFamilyResource):
    key = "mongo.family"
    repository_type = "mongo"

    def _uri(self):
        return self.path

    @cached_property
    def path(self):
        return os.path.join(self.location, self.name)

    def get_last_release_time(self):
        data = self._repository.packages.find_one({'name': self.name}, name_date) or {}
        try:
            return time.mktime(data.get('date').timetuple())
        except AttributeError:
            return 0

    def iter_packages(self):
        data = self._repository.packages.find_one({'name': self.name}, name_versions) or {}

        for d in data.get('payload', []):
            package = self._repository.get_resource(
                MongoPackageResource.key,
                location=self.location,
                name=self.name,
                version=d['version'])
            yield package


class MongoPackageResource(PackageResourceHelper):
    key = "mongo.package"
    variant_key = "mongo.variant"
    repository_type = "mongo"
    schema = package_pod_schema

    def _uri(self):
        obj = VersionedObject.construct(self.name, self.version)
        return "%s:%s" % (self.location, str(obj))

    @property
    def base(self):
        return "%s:%s" % (self.location, self.name)

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

    @cached_property
    def parent(self):
        family = self._repository.get_resource(
            MongoPackageFamilyResource.key,
            location=self.location,
            name=self.name)
        return family

    def _load(self):
        family_data = self._repository.packages.find_one({'name': self.name
                                                          }, name_versions_date_data) or {}

        payload_data = family_data.get('payload', [])
        version_data = None
        expected_version = self.get("version")
        for f in payload_data:
            if expected_version == f['version']:
                return f.get('data', {})


class MongoVariantResource(VariantResourceHelper):
    key = "mongo.variant"
    repository_type = "mongo"

    def _root(self):
        return None  # mongo types do not have 'root'

    @cached_property
    def parent(self):
        package = self._repository.get_resource(
            MongoPackageResource.key,
            location=self.location,
            name=self.name,
            version=self.get("version"))
        return package


class MongoPackageRepository(PackageRepository):

    """
    """
    @classmethod
    def name(cls):
        return "mongo"

    def __init__(self, location, resource_pool):
        """Create a mongo package repository.

        Args:
         location (str): Path containing the package repository.
        """
        # mongo:host=svr,port=1001,namespace=/svr/packages

        settings = config.plugins.package_repository.mongo
        parts = location.split(',', 3)

        host, db_name, port, ns = [settings.host, settings.db_name, settings.port, None]
        for part in parts:
            args = part.split('=', 2)
            if len(args) != 2:
                continue
            k, v = args[0], args[1]
            if k.startswith('host'):
                host = str(v)
            elif k.startswith('db'):
                db_name = str(v)
            elif k.startswith('port'):
                port = int(v)
            elif k.startswith('namespace'):
                ns = str(v)

        if not ns:
            if len(parts) == 1 and parts[0]:
                ns = location
            else:
                raise RuntimeError

        client = MongoClient(host, port)
        db = client[db_name]

        self.packages = db[ns]

        qualified_location = "host=%s,db=%s,port=%s,namespace=%s" % (host, db_name, port, ns)
        super(MongoPackageRepository, self).__init__(qualified_location, resource_pool)
        self.register_resource(MongoPackageFamilyResource)
        self.register_resource(MongoPackageResource)
        self.register_resource(MongoVariantResource)

    def _uid(self):
        return (self.location)

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
        variant = self._create_variant(variant_resource, dry_run=dry_run,
                                       overrides=overrides)
        return variant

    def clear_caches(self):
        super(MongoPackageRepository, self).clear_caches()
        self._get_families.cache_clear()
        self._get_family.cache_clear()
        self._get_packages.cache_clear()
        self._get_variants.cache_clear()

    @lru_cache(maxsize=None)
    def _get_families(self):
        families = []
        names = self.packages.find({}, name_only)
        for name in names:
            family = self.get_resource(
                MongoPackageFamilyResource.key,
                location=self.location,
                name=name['name'])
            families.append(family)
        return families

    @lru_cache(maxsize=None)
    def _get_family(self, name):
        is_valid_package_name(name, raise_error=True)
        pkg = self.packages.find_one({'name': name}, name_only)
        if pkg:
            family = self.get_resource(
                MongoPackageFamilyResource.key,
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

    def _create_family(self, name):
        self.packages.insert({'name': name})
        self.clear_caches()
        return self.get_package_family(name)

    def _create_variant(self, variant, dry_run=False, overrides=None):
        # find or create the package family
        family = self.get_package_family(variant.name)
        was_new = False
        if not family:
            was_new = True
            family = self._create_family(variant.name)

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
        release_data = {}
        new_package_data = variant.parent.validated_data()
        new_package_data.pop("variants", None)
        package_changed = False

        if existing_package:
            existing_package_data = existing_package.validated_data()

            # detect case where new variant introduces package changes
            # outside of variant
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
                        # we should stop here and not install
                        # even when not in dry_run but some UT fails
                        return variant_
                    break

            parent_package = existing_package

            if package_changed:
                # graft together new package data, with existing package
                # variants, and other data that needs to stay unchanged
                # (eg timestamp)
                package_data = new_package_data
                package_data["variants"] = existing_package_data.get("variants", [])
            else:
                package_data = existing_package_data
        else:
            parent_package = variant.parent
            package_data = new_package_data

        if dry_run:
            if was_new:
                self.packages.drop()
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

        # add the timestamp
        overrides = overrides or {}
        overrides["timestamp"] = int(time.time())

        # apply attribute overrides
        for key, value in overrides.iteritems():
            if package_data.get(key) is None:
                package_data[key] = value

        package_data = dict((k, v) for k, v in package_data.iteritems() if v is not None)
        package = {'name': variant.name}
        version = str(variant.version)
        data = package_serialise_schema.validate(package_data)

        latest_package_payload_per_version = -1
        db_pkg = self.packages.find_one(package).get('payload', [])
        if db_pkg:
            # find the latest version data in the array
            # and set it with the new information
            version_data = None
            expected_version = str(variant.version)
            for c, f in enumerate(db_pkg):
                if expected_version == f['version']:
                    latest_package_payload_per_version = c

        if latest_package_payload_per_version == -1:
            db_pkg.append( {'version': version,
                            'data': data
                            }
                         )
        else:
            db_pkg[latest_package_payload_per_version] = {'version': version,
                                                          'data': data
                                                         }

        # utcnow() is the equivalent of touch[ing] the family dir for the filesystem repo.
        # this keeps memcached resolves updated properly
        self.packages.update(package,
                            {
                             '$set': {'date': datetime.datetime.utcnow(),
                                      'payload': db_pkg}},
                            upsert=True)

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
    return MongoPackageRepository
