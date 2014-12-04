from rez.tests.util import TestBase
from rez.resources_ import Resource, ResourcePool, ResourceHandle, Required
from rez.exceptions import ResourceError
import rez.vendor.unittest2 as unittest
from rez.vendor.schema.schema import Schema, Use, And, Optional


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


pet_schema_keys = set(x._schema for x in pet_schema._schema)


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


class PetRepository(object):
    def __init__(self, pool):
        self.pool = pool
        self.pool.register_resource(KittenResource)
        self.pool.register_resource(PuppyResource)

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


class Kitten(object):
    pass


class Puppy(object):
    pass


class PetStore(object):
    def __init__(self):
        self.pool = ResourcePool(cache_size=None)
        self.repo = PetRepository(self.pool)

    def get_kitten(self, name):
        return self._get_pet("kitten", Kitten, name)

    def get_puppy(self, name):
        return self._get_pet("puppy", Puppy, name)

    def _get_pet(self, species, cls_, name):
        fn = getattr(self.repo, "get_%s" % species)
        resource = fn(name)

        #return cls_(resource) if resource else None
        return resource


# -- test suite

class TestResources_(TestBase):
    def test_1(self):
        """resource registration test."""
        pool = ResourcePool(cache_size=None)

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
        pool = ResourcePool(cache_size=None)
        pool.register_resource(ResourceA)
        pool.register_resource(ResourceB)

        # test that resource matches our request, and its data isn't loaded
        variables = dict(foo="hey", bah="ho")
        resource = pool.get_resource("resource.a", variables)
        self.assertTrue(isinstance(resource, ResourceA))
        self.assertEqual(resource.variables, variables)

        # test that a request via a resource's own handle gives the same resource
        resource_ = pool.get_resource_from_handle(resource.handle)
        self.assertTrue(resource_ is resource)

        # test that the same request again gives the cached resource
        resource_ = pool.get_resource("resource.a", variables)
        self.assertTrue(resource_ is resource)

        # clear caches, then test that the same request gives a new resource
        pool.clear_caches()
        resource_ = pool.get_resource("resource.a", variables)
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
            expected_validations = dict((k, 1) for k, v in expected_data.iteritems()
                                        if v is not None)
            self.assertEqual(resource.validations, expected_validations)

        store = PetStore()
        obi = store.get_kitten("obi")
        self.assertTrue(isinstance(obi, KittenResource))
        self.assertFalse(obi.is_loaded)

        obi_ = store.get_kitten("obi")
        self.assertTrue(obi_ is obi)

        # accessing 'name' should not cause a resource data load
        #self.assertEqual(obi.name, "obi")
        #self.assertFalse(obi.resource.is_loaded)

        # accessing an attrib should cause resource's data to load
        self.assertEqual(obi.colors, set(["black", "white"]))
        self.assertEqual(obi.validations, dict(colors=1))
        self.assertTrue(obi.is_loaded)

        # accessing same attrib again should not cause a revalidation
        self.assertEqual(obi.colors, set(["black", "white"]))
        self.assertEqual(obi.validations, dict(colors=1))

        # validated attribs should stay cached
        obi_ = None
        obi = None
        obi = store.get_kitten("obi")
        self.assertEqual(obi.colors, set(["black", "white"]))
        self.assertEqual(obi.validations, dict(colors=1))

        self.assertEqual(obi.male, True)
        self.assertEqual(obi.validations, dict(colors=1, male=1))

        _validate(obi, dict(name="obi",
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
        self.assertTrue(isinstance(taco, PuppyResource))
        self.assertEqual(taco.male, True)
        self.assertEqual(taco.colors, set(["brown"]))


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestResources_("test_1"))
    suite.addTest(TestResources_("test_2"))
    suite.addTest(TestResources_("test_3"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
