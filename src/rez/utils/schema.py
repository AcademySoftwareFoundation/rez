"""
Utilities for working with dict-based schemas.
"""
from rez.vendor.schema.schema import Schema


# an alias which just so happens to be the same number of characters as
# 'Optional' so that our schema are easier to read
Required = Schema


def schema_keys(schema):
    """Get the string values of keys in a dict-based schema.

    Returns:
        Set of string keys of a schema which is in the form (eg):

            schema = Schema({Required("foo"): int,
                             Optional("bah"): basestring})
    """
    def _get_leaf(value):
        if isinstance(value, Schema):
            return _get_leaf(value._schema)
        return value

    return set(_get_leaf(x) for x in _get_leaf(schema))


