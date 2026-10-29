# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'util' module
"""
import os
import sys
from rez.tests.util import TestBase, TempdirMixin
from rez.util import load_module_from_file, resolve_variant_indices


class TestLoadModuleFromFile(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.settings = dict()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_load_module(self) -> None:
        """Ensure that the imported module does not show up in sys.modules"""
        # Random chars are used in the module name to ensure that the module name is unique
        # and the test won't fail because some other module with the same name
        # shows up in sys.modules
        module = 'utils_test_7cd3a335'

        filename = '{0}.py'.format(module)

        with open(os.path.join(self.root, filename), 'w') as fd:
            fd.write('')

        load_module_from_file(module, os.path.join(self.root, filename))
        self.assertEqual(sys.modules.get(module), None, msg='Module was found in sys.modules')


class TestResolveVariantIndices(TestBase):
    """Unit tests for resolve_variant_indices()."""

    def test_positive_indices_passthrough(self) -> None:
        resolved, invalid = resolve_variant_indices([0, 1], 2)
        self.assertEqual(resolved, {0, 1})
        self.assertEqual(invalid, [])

    def test_negative_index_last(self) -> None:
        resolved, invalid = resolve_variant_indices([-1], 3)
        self.assertEqual(resolved, {2})
        self.assertEqual(invalid, [])

    def test_negative_index_first(self) -> None:
        resolved, invalid = resolve_variant_indices([-3], 3)
        self.assertEqual(resolved, {0})
        self.assertEqual(invalid, [])

    def test_duplicate_positive_and_negative(self) -> None:
        """1 and -1 on a 2-variant package both resolve to index 1."""
        resolved, invalid = resolve_variant_indices([1, -1], 2)
        self.assertEqual(resolved, {1})
        self.assertEqual(invalid, [])

    def test_mixed_positive_and_negative(self) -> None:
        resolved, invalid = resolve_variant_indices([0, -1], 3)
        self.assertEqual(resolved, {0, 2})
        self.assertEqual(invalid, [])

    def test_invalid_index_too_large(self) -> None:
        resolved, invalid = resolve_variant_indices([5], 2)
        self.assertEqual(invalid, [5])

    def test_invalid_index_too_negative(self) -> None:
        resolved, invalid = resolve_variant_indices([-3], 2)
        self.assertEqual(invalid, [-3])

    def test_multiple_invalid_sorted(self) -> None:
        """Invalid indices are returned sorted for deterministic error messages."""
        resolved, invalid = resolve_variant_indices([-3, 5], 2)
        self.assertEqual(invalid, [-3, 5])

    def test_zero_num_variants_passthrough(self) -> None:
        """When the package has no explicit variants the input is returned unchanged."""
        resolved, invalid = resolve_variant_indices([0], 0)
        self.assertEqual(resolved, {0})
        self.assertEqual(invalid, [])
