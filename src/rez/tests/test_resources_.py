"""
test core resource system
"""
from rez.tests.util import TestBase
from rez.utils.resources import Resource, ResourcePool, ResourceHandle, \
    ResourceWrapper
from rez.package_repository import PackageRepository
from rez.utils.schema import Required
from rez.exceptions import ResourceError
import unittest
from rez.vendor.schema.schema import Schema, Use, And, Optional
from rez.vendor.six import six


basestring = six.string_types[0]


class PetResourceError(Exception):
    pass


class ResourceA(Resource):
    key = "resource.a"


class ResourceB(Resource):
    key = "resource.b"


class ResourceBad(Resource):
    key = "resource.a"


# here we are simulating a resource repository, in reality this might be a
# database or filesystem.
pets = dict(
    kitten=dict(
        obi=dict(colors=["black", "white"], male=True, age=1.0),
        scully=dict(colors=["tabby"], male=False, age=0.5),
        mordor=dict(colors=["black"], male=True, age="infinite")),  # bad data
    puppy=dict(
        taco=dict(colors=["brown"], male=True, age=0.6, owner="joe.bloggs"),
        ringo=dict(colors=["white", "grey"], male=True, age=0.8)))


pet_schema = Schema({
    Required("name"):       basestring,
    Required("colors"):     And([basestring], Use(set)),
    Required("male"):       bool,
    Required("age"):        float,
    Optional("owner"):      basestring
})


class BasePetResource(Resource):
    schema_error = PetResourceError

    def __init__(self, variables=None):
        super(BasePetResource, self).__init__(variables)
        self.validations = {}

    # tracks validations
    def _validate_key(self, key, attr, key_schema):
        self.validations[key] = self.validations.get(key, 0) + 1
        return self._validate_key_impl(key, attr, key_schema)


class PetResource(BasePetResource):
    schema = pet_schema

    def __init__(self, variables):
        super(PetResource, self).__init__(variables)
        self.is_loaded = False

    def _load(self):
        assert not self.is_loaded
        name = self.variables["name"]
        data = pets[self.key][name]
        data["name"] = name
        self.is_loaded = True
        return data


class KittenResource(PetResource):
    key = "kitten"


class PuppyResource(PetResource):
    key = "puppy"


class PetPool(ResourcePool):
    # don't want to define get_resource on normal pool object anymore,
    # because it's dangerous, since we always want ResourceHandle creation to
    #  go through the PackageRepository.make_resource_handle (so resource
    # classes can normalize them). But for testing, this is handy...
    def get_resource(self, resource_key, variables=None):
        variables = variables or {}
        handle = ResourceHandle(resource_key, variables)
        return self.get_resource_from_handle(handle)


class PetRepository(PackageRepository):
    def __init__(self, pool):
        self.pool = pool
        self.pool.register_resource(KittenResource)
        self.pool.register_resource(PuppyResource)
        self.location = 'Pets R Us'

    @classmethod
    def name(cls):
        return "pet_repository"

    def get_kitten(self, name):
        return self._get_pet("kitten", name)

    def get_puppy(self, name):
        return self._get_pet("puppy", name)

    def _get_pet(self, species, name):
        entries = pets.get(species)
        if entries is None:
            return None
        entry = entries.get(name)
        if entry is None:
            return None

        handle = ResourceHandle(species, dict(name=name))
        return self.pool.get_resource_from_handle(handle)


class Pet(ResourceWrapper):
    keys = ("colors", "male", "age", "owner")

    @property
    def name(self):
        return self.resource.get("name")

    @property
    def is_loaded(self):
        return self.resource.is_loaded


class Kitten(Pet):
    pass


class Puppy(Pet):
    pass


class PetStore(object):
    def __init__(self):
        self.pool = PetPool(cache_size=None)
        self.repo = PetRepository(self.pool)

    def get_kitten(self, name):
        return self._get_pet("kitten", Kitten, name)

    def get_puppy(self, name):
        return self._get_pet("puppy", Puppy, name)

    def _get_pet(self, species, cls_, name):
        fn = getattr(self.repo, "get_%s" % species)
        resource = fn(name)
        resource._repository = self.repo

        return cls_(resource) if resource else None


# -- test suite

class TestResources_(TestBase):
    def test_1(self):
        """resource registration test."""
        pool = PetPool(cache_size=None)

        with self.assertRaises(ResourceError):
            pool.get_resource("resource.a")

        pool.register_resource(ResourceA)
        pool.register_resource(ResourceB)

        with self.assertRaises(ResourceError):
            pool.register_resource(ResourceBad)

        resource_a = pool.get_resource("resource.a")
        resource_b = pool.get_resource("resource.b")
        self.assertTrue(isinstance(resource_a, ResourceA))
        self.assertTrue(isinstance(resource_b, ResourceB))

    def test_2(self):
        """basic resource loading test."""
        repo = PetRepository(PetPool(cache_size=None))
        repo.pool.register_resource(ResourceA)
        repo.pool.register_resource(ResourceB)

        # test that resource matches our request, and its data isn't loaded
        variables = dict(foo="hey", bah="ho", repository_type='pet_repository',
                         location='Pets R Us')
        resource = repo.get_resource("resource.a", **variables)
        self.assertTrue(isinstance(resource, ResourceA))
        self.assertEqual(resource.variables, variables)

        # test that a request via a resource's own handle gives the same resource
        resource_ = repo.get_resource_from_handle(resource.handle)
        self.assertTrue(resource_ is resource)

        # test that the same request again gives the cached resource
        resource_ = repo.get_resource("resource.a", **variables)
        self.assertTrue(resource_ is resource)

        # clear caches, then test that the same request gives a new resource
        repo.clear_caches()
        resource_ = repo.get_resource("resource.a", **variables)
        self.assertEqual(resource_.variables, variables)
        self.assertTrue(resource_ is not resource)

    def test_3(self):
        """real world(ish) example of a resource system.

        In this example, `pets` is a resource repository - in a real resource
        system this might be a filesystem or database, so resource caching is a
        potentially large optimisation.

        `Pet.schema` is used to validate the resource data. It also transforms
        the 'color' entry from a list to a set - not worth caching in this example,
        but in a real resource system, data validation and conversion may be
        expensive.

        `Kitten` and `Puppy` are resource wrappers - as well as providing a single
        class to hide potentially multiple resource classes, they also implement
        the `name` attribute, which means we can query a resource for its name,
        without causing the resource data to be loaded.
        """
        def _validate(resource, expected_data):
            self.assertEqual(resource.validated_data(), expected_data)

            # after full validation, each attrib should validate exactly once.
            # Those with value None are optional and missing attributes, so were
            # never validated.
            expected_validations = dict((k, 1) for k, v in list(expected_data.items())
                                        if v is not None)
            self.assertEqual(resource.validations, expected_validations)

        store = PetStore()
        obi = store.get_kitten("obi")
        self.assertTrue(isinstance(obi, Kitten))
        self.assertTrue(isinstance(obi.resource, KittenResource))
        self.assertFalse(obi.is_loaded)

        obi_ = store.get_kitten("obi")
        self.assertTrue(obi_ == obi)
        self.assertTrue(obi_.resource is obi.resource)

        # accessing 'name' should not cause a resource data load
        self.assertEqual(obi.name, "obi")
        self.assertFalse(obi.is_loaded)

        # accessing an attrib should cause resource's data to load
        self.assertEqual(obi.colors, set(["black", "white"]))
        self.assertEqual(obi.resource.validations, dict(colors=1))
        self.assertTrue(obi.is_loaded)

        # accessing same attrib again should not cause a revalidation
        self.assertEqual(obi.colors, set(["black", "white"]))
        self.assertEqual(obi.resource.validations, dict(colors=1))

        # validated attribs should stay cached
        obi_ = None
        obi = None
        obi = store.get_kitten("obi")
        self.assertEqual(obi.colors, set(["black", "white"]))
        self.assertEqual(obi.resource.validations, dict(colors=1))

        self.assertEqual(obi.male, True)
        self.assertEqual(obi.resource.validations, dict(colors=1, male=1))

        _validate(obi.resource, dict(name="obi",
                                     colors=set(["black", "white"]),
                                     male=True,
                                     age=1.0,
                                     owner=None))

        # load a bad resource, won't fail til bad attribute is accessed
        mordor = store.get_kitten("mordor")
        self.assertEqual(mordor.male, True)

        with self.assertRaises(PetResourceError):
            getattr(mordor, "age")

        # load a puppy why not?
        taco = store.get_puppy("taco")
        self.assertTrue(isinstance(taco, Puppy))
        self.assertTrue(isinstance(taco.resource, PuppyResource))
        self.assertEqual(taco.male, True)
        self.assertEqual(taco.colors, set(["brown"]))

        _validate(taco.resource, dict(name="taco",
                                      colors=set(["brown"]),
                                      male=True,
                                      age=0.6,
                                      owner="joe.bloggs"))


if __name__ == '__main__':
    unittest.main()


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
