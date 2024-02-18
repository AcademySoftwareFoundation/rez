# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
AWS S3 package repository
"""


import os
import subprocess
import tempfile

from rez.package_repository import PackageRepository
from rez.package_resources import PackageFamilyResource, VariantResourceHelper, \
    PackageResourceHelper, package_pod_schema
from rez.serialise import load_from_file, FileFormat
from rez.utils.formatting import is_valid_package_name
from rez.utils.resources import cached_property
from rez.utils.yaml import load_yaml

from rez.config import config


try:
    import pymongo
except ImportError as error:
    raise error


debug_print = config.debug_printer("resources")


# ------------------------------------------------------------------------------
# settings
# ------------------------------------------------------------------------------


class S3Settings(dict):
    """ S3 settings. """

    def __init__(self):
        super().__init__()

        filename = os.path.join(os.path.dirname(__file__), "settings.yaml")
        if os.path.exists(filename):
            self.update(load_yaml(filename))


_settings = S3Settings()


# ------------------------------------------------------------------------------
# resources
# ------------------------------------------------------------------------------


class S3PackageResource(PackageResourceHelper):
    key = "s3.package"
    variant_key = "s3.variant"
    repository_type = "s3"
    schema = package_pod_schema

    def _uri(self):
        return self.path

    @cached_property
    def parent(self):
        family = self._repository.get_resource(
            S3PackageFamilyResource.key,
            location=self.location,
            name=self.name
        )
        return family

    @property
    def base(self):
        return self.path

    @cached_property
    def path(self):
        version = self.get("version")

        result = self._repository.server.find_one({"name": self.name, "version": version})
        location = result.get("location")

        path = self.location

        if location:
            path += f"/{location}"

        path += f"/{self.name}"

        if version:
            path += f"/{version}"

        return path

    def _load(self):
        result = self._repository.server.find_one(
            dict(
                name=self.name,
                version=self.get("version")
            )
        )

        filename = tempfile.NamedTemporaryFile(prefix=self.name, suffix=".py").name
        with open(filename, "w") as stream:
            stream.write(result.get("data"))

        return load_from_file(filename, FileFormat.py)


class S3VariantResource(VariantResourceHelper):
    key = "s3.variant"
    repository_type = "s3"

    @cached_property
    def parent(self):
        package = self._repository.get_resource(
            S3PackageResource.key,
            location=self.location,
            name=self.name,
            version=self.get("version"))

        return package

    def _root(self, ignore_shortlinks=False):
        return self.parent.path

    def _load(self):
        return {}

    def install(self, location=None):
        try:
            subprocess.call([
                "aws", "s3", "sync", self.root, location
            ], shell=True)
        except Exception as error:
            raise error


class S3PackageFamilyResource(PackageFamilyResource):
    key = "s3.family"
    repository_type = "s3"

    def _uri(self):
        return self.path

    @cached_property
    def path(self):
        return f"{self.location}/{self.name}"

    def _iter_packages(self):
        for result in self._repository.server.find({"name": self.name}):
            yield result

    def iter_packages(self):
        for row in self._iter_packages():
            package = self._repository.get_resource(
                S3PackageResource.key,
                location=self.location,
                name=self.name,
                version=row.get("version")
            )
            yield package


# ------------------------------------------------------------------------------
# server
# ------------------------------------------------------------------------------


class Server:
    """ Base class for a server instance.
    
    Note:

        This class is meant to provide an interface to different servers
        containing rez module data.
    """

    def __init__(self, location):
        """ Create a server instance.
        
        Args:
            location (str): Location of the server.
        """
        self.location = self.format_location(location)

    @classmethod
    def name(cls):
        """ Return the name of the server. """
        raise NotImplementedError

    @cached_property
    def connection(self):
        """ Return the connection to the server. """
        raise NotImplementedError

    @classmethod
    def _format_location(cls, location):
        return location

    @classmethod
    def format_location(cls, location):
        return cls._format_location(location)

    @classmethod
    def load(cls, location):
        """ Create and return a server instance. """
        name, loc = location.split("-")

        for server in cls.__subclasses__():
            if server.name() == name:
                return server(loc)

        return cls(loc)

    def find(self, *args, **kwargs):
        raise NotImplementedError

    def find_one(self, *args, **kwargs):
        raise NotImplementedError


class MongoDB(Server):

    @classmethod
    def name(cls):
        """ Return the name of the server. """
        return "mongodb"

    @classmethod
    def _format_location(cls, location):
        # construct location settings
        settings = _settings.get(MongoDB.name(), {})
        settings["location"] = location

        loc = "mongodb://{user}:{pass}@{location}/" \
            "?authMechanism=DEFAULT" \
            "&authSource={authSource}".format(**settings)

        return loc

    @cached_property
    def connection(self):
        client = pymongo.MongoClient(self.location)
        return client.pypiserver_info

    @cached_property
    def cursor(self):
        return self.connection.packages

    def find(self, *args, **kwargs):
        return [x for x in self.cursor.find(*args, **kwargs)]

    def find_one(self, *args, **kwargs):
        return self.cursor.find_one(*args, **kwargs)


# ------------------------------------------------------------------------------
# repository
# ------------------------------------------------------------------------------


class S3PackageRepository(PackageRepository):
    """ S3 class. """

    def __init__(self, location, resource_pool):
        super().__init__(location, resource_pool)

        # construct the associated server instance.
        self.server = Server.load(_settings.get(location))

        self.register_resource(S3PackageFamilyResource)
        self.register_resource(S3PackageResource)
        self.register_resource(S3VariantResource)

    @classmethod
    def name(cls):
        """ Return the name of the package repository type. """
        return "s3"

    def __str__(self):
        return "%s@%s" % (self.name(), self.server.location)
                
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
        """ Returns a family resource for name. """
        is_valid_package_name(name)

        return self.get_resource(
            S3PackageFamilyResource.key,
            location=self.location,
            name=name
        )
            

def register_plugin():
    return S3PackageRepository
