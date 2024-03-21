# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

import subprocess

from rez.artifact_repository import ArtifactRepository


class S3ArtifactRepository(ArtifactRepository):
    """A S3-based artifact repository.
    """

    @classmethod
    def name(cls):
        return "s3"

    def variant_exists(self, variant_resource):
        """Returns if a variant resource exists.
        """
        return True

    def copy_variant_to_path(self, variant_resource, path):
        """Copy a variant resource from the repository.
        """
        try:
            subprocess.call([
                "aws", "s3", "sync", variant_resource.root, path
            ], shell=True)
        except Exception as error:
            raise error

    def copy_variant_from_path(self, variant_resource, path):
        """Copy a variant resource to the repository.
        """
        try:
            subprocess.call([
                "aws", "s3", "sync", path, variant_resource.root
            ], shell=True)
        except Exception as error:
            raise error


def register_plugin():
    return S3ArtifactRepository
