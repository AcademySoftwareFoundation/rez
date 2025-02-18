# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Utilities for working with dict-based schemas.
"""
from rez.vendor.schema.schema import Schema, Optional, Use, And
from rez.config import Validatable


# an alias which just so happens to be the same number of characters as
# 'Optional' so that our schema are easier to read
Required = Schema


def schema_keys(schema):
    """Get the string values of keys in a dict-based schema.

    Non-string keys are ignored.

    Returns:
        set[str]: Set of string keys of a schema which is in the form (eg):

        .. code-block:: python

           schema = Schema({Required("foo"): int,
                            Optional("bah"): str})
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
        if isinstance(key_, str):
            keys.add(key_)

    return keys


def dict_to_schema(schema_dict, required, allow_custom_keys=True, modifier=None):
    """Convert a dict of Schemas into a Schema.

    Args:
        required (bool): Whether to make schema keys optional or required.
        allow_custom_keys (typing.Optional[bool]): If True, creates a schema that
            allows custom items in dicts.
        modifier (typing.Optional[typing.Callable]): Functor to apply to dict values - it is applied
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
                if isinstance(k, str):
                    k = Required(k) if required else Optional(k)
                d[k] = _to(v)
            if allow_custom_keys:
                d[Optional(str)] = modifier or object
            schema: Validatable = Schema(d)
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
        Optional(str): object
    }

    result.update(schema_dict)
    return result
