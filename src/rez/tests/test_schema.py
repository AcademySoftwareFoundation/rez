# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test schema validation and rez.utils.schema helpers
"""
from rez.tests.util import TestBase
from rez.utils.schema import (
    Required,
    dict_to_schema,
    extensible_schema_dict,
    schema_keys,
)
from rez.vendor.schema import And, Optional, Or, Schema, SchemaError, Use


class TestSchema(TestBase):
    def test_basic_types_and_validators(self):
        self.assertEqual(Schema(int).validate(123), 123)
        with self.assertRaises(SchemaError):
            Schema(int).validate("123")

        self.assertEqual(Schema(And(str, len)).validate("abc"), "abc")
        with self.assertRaises(SchemaError):
            Schema(And(str, len)).validate("")

        self.assertEqual(Schema(Or(int, float)).validate(1.5), 1.5)
        with self.assertRaises(SchemaError):
            Schema(Or(int, float)).validate("bad")

        self.assertEqual(Schema(Use(int)).validate("42"), 42)
        with self.assertRaises(SchemaError):
            Schema(Use(int)).validate("not_an_int")

    def test_dict_required_optional_and_defaults(self):
        s = Schema({
            "name": str,
            Optional("count", default=1): int,
        })
        self.assertEqual(s.validate({"name": "rez"}), {"name": "rez", "count": 1})
        self.assertEqual(s.validate({"name": "rez", "count": 5}), {"name": "rez", "count": 5})

        with self.assertRaises(SchemaError):
            s.validate({})
        with self.assertRaises(SchemaError):
            s.validate({"name": "rez", "extra": 2})

    def test_ignore_extra_keys(self):
        s = Schema({"name": str}, ignore_extra_keys=True)
        self.assertEqual(s.validate({"name": "rez", "extra": 2}), {"name": "rez"})

    def test_rez_extensible_schema_priority(self):
        # Optional(str) is inserted before Optional("foo"); specific key must still run first.
        s = Schema(extensible_schema_dict({Optional("foo"): int}))
        self.assertEqual(s.validate({"foo": 3, "other": "ok"}), {"foo": 3, "other": "ok"})
        with self.assertRaises(SchemaError):
            s.validate({"foo": "not_an_int"})

    def test_dict_to_schema_and_schema_keys(self):
        raw = {"a": int, "nested": {"b": str}}
        s = dict_to_schema(raw, required=False, allow_custom_keys=True)
        self.assertEqual(
            s.validate({"a": 1, "nested": {"b": "x", "extra": 9}, "custom": True}),
            {"a": 1, "nested": {"b": "x", "extra": 9}, "custom": True},
        )
        with self.assertRaises(SchemaError):
            s.validate({"a": "bad"})

        self.assertEqual(schema_keys(Schema({Required("foo"): int, Optional("bar"): str})), {"foo", "bar"})
