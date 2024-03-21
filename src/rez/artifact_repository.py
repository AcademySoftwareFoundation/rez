# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

from rez.plugin_managers import plugin_manager


class ArtifactRepository(object):
    """Base class for artifact repositories implement in the artifact_repository
    plugin type.
    """

    @classmethod
    def name(cls):
        """Return the name of the artifact repository type."""
        raise NotImplementedError

    def __init__(self, location):
        """Create an artifact repository.
        
        Args:
            location (str): Path containing the artifact repository.
        """
        self.location = location

    def __str__(self):
        return "%s@%s" % (self.name(), self.location)

    def __eq__(self, other):
        return (
            isinstance(other, ArtifactRepository)
            and other.name() == self.name()
        )

    def variant_exists(self, variant_resource):
        """Returns if a variant resource exists.
        """
        raise NotImplementedError

    def copy_variant_to_path(self, variant_resource, path):
        """Copy a variant resource from the repository.
        """
        raise NotImplementedError

    def copy_variant_from_path(self, variant_resource):
        """Copy a variant resource to the repository.
        """
        raise NotImplementedError


class ArtifactRepositoryManager(object):
    """Artifact repository manager.
    
    Manages retrieval of resources (package and variants) from `ArtifactRepository`
    instances.
    """

    def __init__(self):
        """Create an artifact repo manager.
        """
        self.repositories = {}

    def _get_repository(self, path, **repo_args):
        repo_type, location = path.split("@", 1)
        cls = plugin_manager.get_plugin_class("artifact_repository", repo_type)
        repo = cls(location, **repo_args)
        return repo

    def get_repository(self, path):
        """Get an artifact repository.
        
        Args:
            path (str): A string in the form "type@location", where
                'type' identifies the repository plugin type to use.

        Returns:
            `ArtifactRepository` instance.
        """
        # get possibly cached repo
        repository = self.repositories.get(path)

        # create and cache if not already cached
        if not repository:
            repository = self._get_repository(path)
            self.repositories[path] = repository

        return repository


# singleton
artifact_repository_manager = ArtifactRepositoryManager()
