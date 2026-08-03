# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test package maker.
"""
import os

from rez.tests.util import TestBase, TempdirMixin
from rez.package_maker import make_package


class TestPackages(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

        cls.settings = dict()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def test_make_package(self):
        '''Test make_package makes a package in structure we expect'''
        def make_root(variant, root):
            assert os.path.isdir(root)
            assert variant.resource.repository_type == 'memory'

            with open(os.path.join(root, 'payload.txt'),'w'):
                pass

        with make_package('test_package1', self.root, make_root=make_root) as pkg:
            pkg.version = '1.0.0'

        assert os.path.isfile(os.path.join(self.root, 'test_package1', '1.0.0', 'package.py'))
        assert os.path.isfile(os.path.join(self.root, 'test_package1', '1.0.0', 'payload.txt'))

    def test_make_package_with_variant(self):
        '''Test make_package makes a package with variants sub path'''
        def make_root(variant, root):
            with open(os.path.join(root, 'payload.txt'),'w'):
                pass

        with make_package('test_package2', self.root, make_root=make_root) as pkg:
            pkg.version = '1.0.1'
            pkg.variants = [['python-3']]

        payload_path = os.path.join(self.root, 'test_package2', '1.0.1', 'python-3', 'payload.txt')
        assert os.path.isfile(payload_path)

    def test_make_package_build_token(self):
        '''Test make_package has a build prefix token while building payload'''
        def make_base(variant, base):
            assert os.path.isdir(base)
            assert os.path.isfile(os.path.join(os.path.dirname(base), '.building2.0.1'))

        with make_package('test_package3', self.root, make_base=make_base) as pkg:
            pkg.version = '2.0.1'
