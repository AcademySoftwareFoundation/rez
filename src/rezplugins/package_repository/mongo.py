# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import time
from tempfile import NamedTemporaryFile
from urllib.parse import quote_plus
import datetime
from tempfile import gettempdir

from rez.artifact_repository import artifact_repository_manager
from rez.config import config
from rez.exceptions import RezError, PackageRepositoryError
from rez.packages import Version
from rez.package_repository import PackageRepository
from rez.package_resources_ import PackageFamilyResource, VariantResourceHelper,\
    PackageResourceHelper, package_pod_schema
from rez.serialise import load_from_file, FileFormat
from rez.utils.resources import cached_property
from rez.vendor.six import six

from pymongo import MongoClient
from pymongo.uri_parser import SCHEME


basestring = six.string_types[0]

debug_print = config.debug_printer("resources")


# ------------------------------------------------------------------------------
# exceptions
# ------------------------------------------------------------------------------


class MongoUrlError(RezError):
    """There is an error related to the Mongo url.
    """
    pass


# ------------------------------------------------------------------------------
# utilities
# ------------------------------------------------------------------------------


def _format(uri):
    username = quote_plus(os.getenv("REZ_MONGO_USERNAME", ""))
    password = quote_plus(os.getenv("REZ_MONGO_PASSWORD", ""))
    
    if username and password:
        uri = username + ":" + password + "@" + uri
    
    if not uri.startswith(SCHEME):
        uri = SCHEME + uri
        
    return uri


# ------------------------------------------------------------------------------
# resources
# ------------------------------------------------------------------------------


class MongoPackageFamilyResource(PackageFamilyResource):
    key = "mongo.family"
    repository_type = "mongo"

    def _uri(self):
        return self.location

    def get_last_release_time(self):
        res = self._repository.packages.find_one({"name": self.name}) or {}
        try:
            return time.mktime(res.get("timestamp").timetuple())
        except AttributeError:
            return 0

    def _iter_packages(self):
        for res in self._repository.packages.find({"name": self.name}):
            yield res

    def iter_packages(self):
        for res in self._iter_packages():
            yield self._repository.get_resource(
                MongoPackageResource.key,
                location=self.location,
                name=self.name,
                version=res.get("version")
            )


class MongoPackageResource(PackageResourceHelper):
    key = "mongo.package"
    variant_key = "mongo.variant"
    repository_type = "mongo"
    schema = package_pod_schema

    def _uri(self):
        return self.location

    @cached_property
    def parent(self):
        return self._repository.get_resource(
            MongoPackageFamilyResource.key,
            location=self.location,
            name=self.name
        )

    @cached_property
    def path(self):
        version = self.get("version")

        res = self._repository.packages.find_one({"name": self.name, "version": version})
        location = res.get("location")
        repo_type, location = location.split('@', 1)
        path = location + "/" + self.name

        if version:
            path += "/" + version

        return path
    
    @property
    def base(self):
        return self.path

    def _load(self):
        res = self._repository.packages.find_one({"name": self.name, "version": self.get("version")})
        if not res:
            return {}

        file = NamedTemporaryFile(prefix=self.name, suffix=".py").name
        with open(file, "w") as stream:
            stream.write(res.get("data"))

        return load_from_file(file, FileFormat.py)


class MongoVariantResource(VariantResourceHelper):
    key = "mongo.variant"
    repository_type = "mongo"

    @cached_property
    def parent(self):
        return self._repository.get_resource(
            MongoPackageResource.key,
            location=self.location,
            name=self.name,
            version=self.get("version")
        )

    def _root(self, ignore_shortlinks=False):
        return self.parent.path

    def _load(self):
        return {}

    def install(self, location=None):
        """Install resource to a location.
        """
        res = self._repository.packages.find_one({"name": self.name, "version": self.get("version")})
        repo = artifact_repository_manager.get_repository(res.get("location"))
        repo.copy_variant_to_path(self, location)


# ------------------------------------------------------------------------------
# repository
# ------------------------------------------------------------------------------


class MongoPackageRepository(PackageRepository):
    """A Mongo-based package repository.

    Package information is stored in a Mongo collection and points
    to a payload within an artifact repository.

        {
            "_id": {
                "$oid": ObjectId(...)
            },
            "name": "foo",
            "version": "1.0.0",
            "location": "s3@s3://bucket-1",
            "data": ""
        }
    """

    @classmethod
    def name(cls):
        return "mongo"

    def __init__(self, location, resource_pool):
        """Create a mongo package repository.

        Args:
            location (str): Path containing the package repository.
        """
        super().__init__(location, resource_pool)

        client = MongoClient(_format(location))
        db = client.get_default_database()
        self.packages = db.get_collection("packages")

        self.register_resource(MongoPackageFamilyResource)
        self.register_resource(MongoPackageResource)
        self.register_resource(MongoVariantResource)

    def _uid(self):
        return (self.location)

    def find_variant(self, package_family_resource, variant_name, variant_version):
        for package_resource in self.iter_packages(package_family_resource):
            for variant in self.iter_variants(package_resource):
                if variant.name == variant_name and \
                   variant.version == variant_version:
                    return variant

        return None

    def get_variants(self, package_resource):
        return [x for x in package_resource.iter_variants()]

    def iter_variants(self, package_resource):
        for variant in self.get_variants(package_resource):
            yield variant

    def get_parent_package_family(self, package_resource):
        return package_resource.parent

    def get_parent_package(self, variant_resource):
        return variant_resource.parent

    def get_packages(self, package_family_resource):
        return [x for x in package_family_resource.iter_packages()]

    def iter_packages(self, package_family_resource):
        for package in package_family_resource.iter_packages():
            yield package

    def get_package_family(self, name):
        res = self.packages.find_one({"name": name})
        if res:
            family = self.get_resource(
                MongoPackageFamilyResource.key,
                location=self.location,
                name=name
            )
            return family

        return None

    def _get_variant_document(self, variant_resource, overrides=None):
        """Return a variant resource document post from Mongo.
        """
        install_path = self.get_package_payload_path(
                                    variant_resource.name,
                                    variant_resource.version
                                )

        pkg_file = os.path.join(install_path, "package.py")
        with open(pkg_file, "r") as stream:
            data = stream.read()

        res = self.packages.find_one({
                                "name": variant_resource.name,
                                "version": str(variant_resource.version)})

        if not res:
            res = {
                "name": variant_resource.name,
                "version": str(variant_resource.version),
            }

        post = res.copy()
        post = post.update(overrides)
        post["data"] = data
        post["timestamp"] = datetime.datetime.utcnow()

        return post    

    def install_variant(self, variant_resource, artifact_path=None, dry_run=False, overrides=None):
        overrides = overrides or {}

        # Name and version overrides are a special case - they change the
        # destination variant to be created/replaced.
        #
        variant_name = variant_resource.name
        variant_version = variant_resource.version

        variant_location = artifact_path

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

        overrides["location"] = variant_location

        post = self._get_variant_document(variant_resource, overrides)
        post_id = post.get("_id")

        if post_id:
            self.packages.update_one({"_id": post_id}, {"$set": post}, upsert=True)
        else:
            self.packages.insert_one(post)

        variant = self.find_variant(
                        self.get_package_family(variant_name),
                        variant_name,
                        variant_version
                    )

        if not variant:
            raise PackageRepositoryError(
                "Created variant not found.")

        install_path = self.get_package_payload_path(
            variant_name,
            variant_version
        )

        if artifact_path:
            art_repo = artifact_repository_manager.get_repository(artifact_path)
            art_repo.copy_variant_from_path(variant, install_path)

        return variant

    def get_package_payload_path(self, package_name, package_version=None):
        path = os.path.join(gettempdir(), "rez", package_name)

        if package_version:
            path = os.path.join(path, str(package_version))

        return path

 
def register_plugin():
    return MongoPackageRepository
