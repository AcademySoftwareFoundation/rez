# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project
"""
CUSTOM TMA module built for ENVLaunch / Package Releaser requirements
"""

import os
import sys
import shutil
import re
import importlib.util
from importlib import reload
from functools import wraps

from rez.exceptions import PackageNotFoundError, PackageRequestError, PackageMetadataError, ResourceError

def reload_package_py(func):
    """Reloads the package_mod attr in PackageHandler()"""

    @wraps(func)
    def _wrap(*args, **kwargs):
        obj = args[0]
        obj.package_mod = obj._read_package_module()
        return func(*args, **kwargs)
    return _wrap


class PackageHandler():
    """Handles a package's package.py"""

    def __init__(self, pkg_root, name, version):
        self.pkg_root = pkg_root
        self.name = name
        self.version = version

        if not self._validate_package():
            raise PackageNotFoundError('Package "{}" not found'.format(self.package_path))
        
        self.package_mod = self._read_package_module()

    @property
    def package_path(self):
        """Returns the package directory path as string"""
        return os.path.join(self.pkg_root, self.name)
    
    @property
    def package_py_path(self):
        """Returns the package.py path as string"""
        return os.path.join(self.package_path, self.version, 'package.py')
    
    @property
    def package_py_editor(self):
        """Returns an instance of the PackagePyEditor"""
        return PackagePyEditor(self.package_py_path)
    
    def _validate_package(self):
        """Validates the package exists and is valid"""
        if not os.path.isdir(self.package_path):
            return False
        if not os.path.isfile(self.package_py_path):
            return False
        return True
    
    def _read_package_module(self):
        """Reads the package.py as a module, returns it"""
        spec = importlib.util.spec_from_file_location('package_mod', self.package_py_path)
        pkg_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pkg_module)
        return pkg_module

    @reload_package_py
    def get_variant_from_index(self, index):
        """Returns the variant path located at the given variant index
        
        Args:
            index (int): Variant index
            
        Returns:
            list: Variant path
            
        Raises:
            PackageRequestError: Raised if package has no variants, or index not found
        """
        if not hasattr(self.package_mod, 'variants'):
            raise PackageRequestError(
                'Cannot find variant index "{}" in package "{}": No variants defined'.format(index, self.package_path)
                )
        try:
            return self.package_mod.variants[index]
        except IndexError:
            raise PackageRequestError(
                'Variant index "{}" not found in pacakge "{}"'.format(index, self.package_path)
            )

    @reload_package_py
    def fetch_variants(self):
        """Fetches the list of variants
        
        Returns:
            list|None: List of variant(lists), or None if no variants defined
        """
        if hasattr(self.package_mod, 'variants'):
            return self.package_mod.variants
        else:
            return None
    
    @reload_package_py
    def add_variant(self, variant, force=False, exist_ok=False):
        """Add a variant to the local package.py
        NOTE: The variants will be sorted
        
        Args:
            variant (list): Variant subpath to add
            force (bool): If True, forces the variant attribute even if not defined (Defaults to False)
            exist_ok (bool): Returns True even if variant already exists, defaults to False
            
        Returns:
            bool: Variant added?

        Raises:
            PackageMetadataError: Raised if package has no variants defined and force==False
        """
        variants = self.fetch_variants()
        if variants is None and not force:
            raise PackageMetadataError('Package has no variants, cannot add.')
        
        # Validate if already in list
        if variant in variants:
            return True if exist_ok else False
        else:
            variants.append(variant)
            with self.package_py_editor as editor:
                editor.update_variants(variants)
            return True
    
    @reload_package_py
    def remove_variant(self, variant, not_found_ok=False):
        """Removes a variant from the local package.py
        NOTE: The variants will be sorted
        
        Args:
            variant (list): Variant subpath to remove
            not_found_ok (bool): Returns True even if variant not found, defaults to False
            
        Returns:
            bool: Variant removed?

        Raises:
            PackageMetadataError: Raised if package has no variants defined
        """
        variants = self.fetch_variants()
        if variants is None:
            raise PackageMetadataError('Package has no variants attribute defined, cannot remove.')
        
        # Validate if already in list
        if variant not in variants:
            return True if not_found_ok else False
        else:
            variants.remove(variant)
            with self.package_py_editor as editor:
                editor.update_variants(variants)
            return True


class PackagePyEditor():
    """Class to edit a package.py"""

    def __init__(self, file_path):
        """Constructor
        
        Args:
            file_path (str): Package.py file path
        """
        self.file_path = file_path
        self._f = None

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, tb):
        return
    
    def _validate_variants(self, variants):
        """Validates if the variants list is valid
        
        Args:
            variants (list): List of variants
            
        Returns:
            bool: Valid?
        """
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, list):
                    for sub_path in variant:
                        if isinstance(sub_path, str) and sub_path != '':
                            continue
                        else:
                            return False
                else:
                    return False
        else:
            return False
        return True
    
    def update_variants(self, variants, create_if_missing=False):
        """Updates variants in the package.py
        
        Args:
            variants (list): List of variants
            
        Returns:
            bool: Success?
            
        Raises:
            ResourceError: Raised if invalid variants format provided
        """
        if not self._validate_variants(variants):
            raise ResourceError('provided variants must be a list of lists')

        with open(self.file_path, encoding="utf-8") as f:
            lines = f.readlines()

        inside_variants = False
        brackets_count = 0
        start_line = None
        end_line = None

        i = 0
        for line in lines:
            if not inside_variants and re.match(r"^\s*variants\s*=", line):
                inside_variants = True
                start_line = i

            if inside_variants:
                brackets_count += (line.count('[') - line.count(']'))
                if brackets_count == 0:  # end of variants list
                    inside_variants = False
                    end_line = i

            i += 1

        with open(self.file_path, "w", encoding="utf-8") as f:
            f.writelines(lines[0:start_line])

            # Insert variants
            f.write('variants = [\n')
            sorted_variants = sorted(variants)
            for variant in sorted_variants:
                last_variant = sorted_variants.index(variant) + 1 == len(sorted_variants)
                f.write('    ' + str(variant) + ('' if last_variant else ',') + '\n')
            f.write(']\n')

            f.writelines(lines[end_line+1:])

        return True
