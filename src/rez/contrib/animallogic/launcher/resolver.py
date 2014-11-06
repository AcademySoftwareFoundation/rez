from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.resolver import ResolverStatus
from rez.contrib.animallogic.launcher.exceptions import RezResolverError


class RezServiceInterface(object):

    def get_resolved_packages_from_requirements(self, requirements,
                                                timestamp=None,
                                                max_fails=-1):

        raise NotImplementedError


class RezService(RezServiceInterface):

    def get_resolved_packages_from_requirements(self, requirements,
                                                timestamp=None,
                                                max_fails=-1):

        package_paths = [config.release_packages_path]

        resolved_context = ResolvedContext(requirements,
                                           package_paths=package_paths,
                                           timestamp=timestamp,
                                           max_fails=max_fails)

        if resolved_context.status == ResolverStatus.solved:
            return resolved_context.resolved_packages

        raise RezResolverError("Unable to resolve the environment for %s." %
                               requirements)
