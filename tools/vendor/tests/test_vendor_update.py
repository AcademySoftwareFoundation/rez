# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vendor_update


class TestVendorUpdateCLI(unittest.TestCase):
    def test_parse_args_defaults(self):
        args = vendor_update.parse_args([])
        self.assertEqual(args.packages, [])
        self.assertFalse(args.verify)

    def test_parse_args_packages_and_verify(self):
        args = vendor_update.parse_args(["--verify", "six", "schema"])
        self.assertEqual(args.packages, ["six", "schema"])
        self.assertTrue(args.verify)

    def test_requires_python_38_compatible(self):
        self.assertTrue(vendor_update.is_python_compatible(">=3.8", (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible(">=3.7,<4", (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible(None, (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible("", (3, 8)))
        self.assertFalse(vendor_update.is_python_compatible(">=3.9", (3, 8)))
        self.assertFalse(vendor_update.is_python_compatible(">=3.10", (3, 8)))
        self.assertFalse(vendor_update.is_python_compatible("~=3.9", (3, 8)))
        self.assertTrue(vendor_update.is_python_compatible(">=2.7, !=3.0.*, !=3.1.*", (3, 8)))


if __name__ == "__main__":
    unittest.main()
