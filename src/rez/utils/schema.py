"""
Utilities for working with dict-based schemas.
"""
import inspect

from rez.vendor.schema.schema import Schema, Optional, Use, And


# an alias which just so happens to be the same number of characters as
# 'Optional' so that our schema are easier to read
Required = Schema

def _iter_schema_string_keys(schema):
    dict_ = schema._schema
    assert isinstance(dict_, dict)

    def _get_leaf(value):
        if isinstance(value, Schema):
            return _get_leaf(value._schema)
        return value

    for raw_key, val in dict_.iteritems():
        str_key = _get_leaf(raw_key)
        if not isinstance(str_key, basestring):
            str_key = None
        yield str_key, raw_key, val


def schema_keys(schema):
    """Get the string values of keys in a dict-based schema.

    Non-string keys are ignored.

    Returns:
        Set of string keys of a schema which is in the form (eg):

            schema = Schema({Required("foo"): int,
                             Optional("bah"): basestring})
    """
    return set(str_key
               for str_key, raw_key, val in _iter_schema_string_keys(schema)
               if str_key is not None)


def get_sub_schema(schema, key):
    for str_key, raw_key, val in _iter_schema_string_keys(schema):
        if str_key == key:
            return Schema(val)
    raise KeyError(key)


def get_cls_schema(obj):
    if inspect.isclass(obj):
        cls = obj
    else:
        cls = type(obj)
    return getattr(obj, 'schema', None)


def get_cls_sub_schema(obj, key):
    cls_schema = get_cls_schema(obj)
    if cls_schema is None:
        return None
    if not isinstance(getattr(cls_schema, '_schema', None), dict):
        return None
    try:
        return get_sub_schema(cls_schema, key)
    except KeyError:
        return None


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
            for k, v in value.iteritems():
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
