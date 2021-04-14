"""
Utilities for working with dict-based schemas.
"""
from rez.vendor.six import six
from rez.vendor.schema.schema import Schema, Optional, Use, And


basestring = six.string_types[0]


# an alias which just so happens to be the same number of characters as
# 'Optional' so that our schema are easier to read
Required = Schema


def schema_keys(schema):
    """Get the string values of keys in a dict-based schema.

    Non-string keys are ignored.

    Returns:
        Set of string keys of a schema which is in the form (eg):

            schema = Schema({Required("foo"): int,
                             Optional("bah"): basestring})
    """
    def _get_leaf(value):
        if isinstance(value, Schema):
            return _get_leaf(value._schema)
        return value

    keys = set()
    dict_ = schema._schema
    assert isinstance(dict_, dict)

    for key in dict_.keys():
        key_ = _get_leaf(key)
        if isinstance(key_, basestring):
            keys.add(key_)

    return keys


def dict_to_schema(schema_dict, required, allow_custom_keys=True, modifier=None):
    """Convert a dict of Schemas into a Schema.

    Args:
        required (bool): Whether to make schema keys optional or required.
        allow_custom_keys (bool, optional): If True, creates a schema that
            allows custom items in dicts.
        modifier (callable): Functor to apply to dict values - it is applied
            via `Schema.Use`.

    Returns:
        A `Schema` object.
    """
    if modifier:
        modifier = Use(modifier)

    def _to(value):
        if isinstance(value, dict):
            d = {}
            for k, v in value.items():
                if isinstance(k, basestring):
                    k = Required(k) if required else Optional(k)
                d[k] = _to(v)
            if allow_custom_keys:
                d[Optional(basestring)] = modifier or object
            schema = Schema(d)
        elif modifier:
            schema = And(value, modifier)
        else:
            schema = value
        return schema

    return _to(schema_dict)


def extensible_schema_dict(schema_dict):
    """Create schema dict that allows arbitrary extra keys.

    This helps to keep newer configs or package definitions compatible with
    older rez versions, that may not support newer schema fields.
    """
    result = {
        Optional(basestring): object
    }

    result.update(schema_dict)
    return result


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
