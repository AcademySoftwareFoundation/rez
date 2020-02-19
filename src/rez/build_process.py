from __future__ import print_function

from rez.packages import iter_packages
from rez.exceptions import BuildProcessError, BuildContextResolveError, \
    ReleaseHookCancellingError, RezError, ReleaseError, BuildError, \
    ReleaseVCSError, _NeverError
from rez.utils.logging_ import print_warning
from rez.utils.colorize import heading, Printer
from rez.resolved_context import ResolvedContext
from rez.release_hook import create_release_hooks
from rez.resolver import ResolverStatus
from rez.config import config
from rez.vendor.enum import Enum
from contextlib import contextmanager
from pipes import quote
import getpass
import os.path
import sys


debug_print = config.debug_printer("package_release")


def get_build_process_types():
    """Returns the available build process implementations."""
    from rez.plugin_managers import plugin_manager
    return plugin_manager.get_plugins('build_process')


def create_build_process(process_type, working_dir, build_system, package=None,
                         vcs=None, ensure_latest=True, skip_repo_errors=False,
                         ignore_existing_tag=False, verbose=False, quiet=False):
    """Create a `BuildProcess` instance."""
    from rez.plugin_managers import plugin_manager
    process_types = get_build_process_types()
    if process_type not in process_types:
        raise BuildProcessError("Unknown build process: %r" % process_type)

    cls = plugin_manager.get_plugin_class('build_process', process_type)

    return cls(working_dir,  # ignored (deprecated)
               build_system,
               package=package,  # ignored (deprecated)
               vcs=vcs,
               ensure_latest=ensure_latest,
               skip_repo_errors=skip_repo_errors,
               ignore_existing_tag=ignore_existing_tag,
               verbose=verbose,
               quiet=quiet)


class BuildType(Enum):
    """ Enum to represent the type of build."""
    local = 0
    central = 1


class BuildProcess(object):
    """A BuildProcess builds and possibly releases a package.

    A build process iterates over the variants of a package, creates the
    correct build environment for each variant, builds that variant using a
    build system (or possibly creates a script so the user can do that
    independently), and then possibly releases the package with the nominated
    VCS. This is an abstract base class, you should use a BuildProcess
    subclass.
    """
    @classmethod
    def name(cls):
        raise NotImplementedError

    def __init__(self, working_dir, build_system, package=None, vcs=None,
                 ensure_latest=True, skip_repo_errors=False,
                 ignore_existing_tag=False, verbose=False, quiet=False):
        """Create a BuildProcess.

        Args:
            working_dir (DEPRECATED): Ignored.
            build_system (`BuildSystem`): Build system used to build the package.
            package (DEPRECATED): Ignored.
            vcs (`ReleaseVCS`): Version control system to use for the release
                process.
            ensure_latest: If True, do not allow the release process to occur
                if an newer versioned package is already released.
            skip_repo_errors: If True, proceed with the release even when errors
                occur. BE CAREFUL using this option, it is here in case a package
                needs to be released urgently even though there is some problem
                with reading or writing the repository.
            ignore_existing_tag: Perform the release even if the repository is
                already tagged at the current version. If the config setting
                plugins.release_vcs.check_tag is False, this has no effect.
            verbose (bool): Verbose mode.
            quiet (bool): Quiet mode (overrides `verbose`).
        """
        self.verbose = verbose and not quiet
        self.quiet = quiet
        self.build_system = build_system
        self.vcs = vcs
        self.ensure_latest = ensure_latest
        self.skip_repo_errors = skip_repo_errors
        self.ignore_existing_tag = ignore_existing_tag

        if vcs and vcs.pkg_root != self.working_dir:
            raise BuildProcessError(
                "Build process was instantiated with a mismatched VCS instance")

        if os.path.isabs(self.package.config.build_directory):
            self.build_path = self.package.config.build_directory
        else:
            self.build_path = os.path.join(self.working_dir,
                                           self.package.config.build_directory)

    @property
    def package(self):
        return self.build_system.package

    @property
    def working_dir(self):
        return self.build_system.working_dir

    def build(self, install_path=None, clean=False, install=False, variants=None):
        """Perform the build process.

        Iterates over the package's variants, resolves the environment for
        each, and runs the build system within each resolved environment.

        Args:
            install_path (str): The package repository path to install the
                package to, if installing. If None, defaults to
                `config.local_packages_path`.
            clean (bool): If True, clear any previous build first. Otherwise,
                rebuild over the top of a previous build.
            install (bool): If True, install the build.
            variants (list of int): Indexes of variants to build, all if None.

        Raises:
            `BuildError`: If the build failed.

        Returns:
            int: Number of variants successfully built.
        """
        raise NotImplementedError

    def release(self, release_message=None, variants=None):
        """Perform the release process.

        Iterates over the package's variants, building and installing each into
        the release path determined by `config.release_packages_path`.

        Args:
            release_message (str): Message to associate with the release.
            variants (list of int): Indexes of variants to release, all if None.

        Raises:
            `ReleaseError`: If the release failed.

        Returns:
            int: Number of variants successfully released.
        """
        raise NotImplementedError

    def get_changelog(self):
        """Get the changelog since last package release.

        Returns:
            str: Changelog.
        """
        raise NotImplementedError


class BuildProcessHelper(BuildProcess):
    """A BuildProcess base class with some useful functionality.
    """
    @contextmanager
    def repo_operation(self):
        exc_type = ReleaseVCSError if self.skip_repo_errors else _NeverError
        try:
            yield
        except exc_type as e:
            print_warning("THE FOLLOWING ERROR WAS SKIPPED:\n%s" % str(e))

    def visit_variants(self, func, variants=None, **kwargs):
        """Iterate over variants and call a function on each."""
        if variants:
            present_variants = range(self.package.num_variants)
            invalid_variants = set(variants) - set(present_variants)
            if invalid_variants:
                raise BuildError(
                    "The package does not contain the variants: %s"
                    % ", ".join(str(x) for x in sorted(invalid_variants)))

        # iterate over variants
        results = []
        num_visited = 0

        for variant in self.package.iter_variants():
            if variants and variant.index not in variants:
                self._print_header(
                    "Skipping variant %s (%s)..."
                    % (variant.index, self._n_of_m(variant)))
                continue

            # visit the variant
            result = func(variant, **kwargs)
            results.append(result)
            num_visited += 1

        return num_visited, results

    def get_package_install_path(self, path):
        """Return the installation path for a package (where its payload goes).

        Args:
            path (str): Package repository path.
        """
        from rez.package_repository import package_repository_manager

        pkg_repo = package_repository_manager.get_repository(path)

        return pkg_repo.get_package_payload_path(
            package_name=self.package.name,
            package_version=self.package.version
        )

    def create_build_context(self, variant, build_type, build_path):
        """Create a context to build the variant within."""
        request = variant.get_requires(build_requires=True,
                                       private_build_requires=True)

        req_strs = map(str, request)
        quoted_req_strs = map(quote, req_strs)
        self._print("Resolving build environment: %s", ' '.join(quoted_req_strs))

        if build_type == BuildType.local:
            packages_path = self.package.config.packages_path
        else:
            packages_path = self.package.config.nonlocal_packages_path

        # It is uncommon, but possible, to define the package filters in the
        # developer package. Example scenario: you may want to enable visiblity
        # of *.dev packages if the current package is *.dev also, for example
        # (assuming you have a production-time package filter which filters out
        # *.dev packages by default).
        #
        if self.package.config.is_overridden("package_filter"):
            from rez.package_filter import PackageFilterList

            data = self.package.config.package_filter
            package_filter = PackageFilterList.from_pod(data)
        else:
            package_filter = None

        # create the build context
        context = ResolvedContext(request,
                                  package_paths=packages_path,
                                  package_filter=package_filter,
                                  building=True)
        if self.verbose:
            context.print_info()

        # save context before possible fail, so user can debug
        rxt_filepath = os.path.join(build_path, "build.rxt")
        context.save(rxt_filepath)

        if context.status != ResolverStatus.solved:
            raise BuildContextResolveError(context)
        return context, rxt_filepath

    def pre_release(self):
        release_settings = self.package.config.plugins.release_vcs

        # test that the release path exists
        release_path = self.package.config.release_packages_path
        if not os.path.exists(release_path):
            raise ReleaseError("Release path does not exist: %r" % release_path)

        # test that the repo is in a state to release
        if self.vcs:
            self._print("Checking state of repository...")
            with self.repo_operation():
                self.vcs.validate_repostate()

            # check if the repo is already tagged at the current version
            if release_settings.check_tag and not self.ignore_existing_tag:
                tag_name = self.get_current_tag_name()
                tag_exists = False
                with self.repo_operation():
                    tag_exists = self.vcs.tag_exists(tag_name)

                if tag_exists:
                    raise ReleaseError(
                        "Cannot release - the current package version '%s' is "
                        "already tagged in the repository. Use --ignore-existing-tag "
                        "to force the release" % self.package.version)

        it = iter_packages(self.package.name, paths=[release_path])
        packages = sorted(it, key=lambda x: x.version, reverse=True)

        # check UUID. This stops unrelated packages that happen to have the same
        # name, being released as though they are the same package
        if self.package.uuid and packages:
            latest_package = packages[0]
            if latest_package.uuid and latest_package.uuid != self.package.uuid:
                raise ReleaseError(
                    "Cannot release - the packages are not the same (UUID mismatch)")

        # test that a newer package version hasn't already been released
        if self.ensure_latest:
            for package in packages:
                if package.version > self.package.version:
                    raise ReleaseError(
                        "Cannot release - a newer package version already "
                        "exists (%s)" % package.uri)
                else:
                    break

    def post_release(self, release_message=None):
        tag_name = self.get_current_tag_name()

        if self.vcs is None:
            return  # nothing more to do

        # write a tag for the new release into the vcs
        with self.repo_operation():
            self.vcs.create_release_tag(tag_name=tag_name, message=release_message)

    def get_current_tag_name(self):
        release_settings = self.package.config.plugins.release_vcs
        try:
            tag_name = self.package.format(release_settings.tag_name)
        except Exception as e:
            raise ReleaseError("Error formatting release tag name: %s" % str(e))
        if not tag_name:
            tag_name = "unversioned"
        return tag_name

    def run_hooks(self, hook_event, **kwargs):
        hook_names = self.package.config.release_hooks or []
        hooks = create_release_hooks(hook_names, self.working_dir)

        for hook in hooks:
            debug_print("Running %s hook '%s'...",
                        hook_event.label, hook.name())
            try:
                func = getattr(hook, hook_event.__name__)
                func(user=getpass.getuser(), **kwargs)
            except ReleaseHookCancellingError as e:
                raise ReleaseError(
                    "%s cancelled by %s hook '%s': %s:\n%s"
                    % (hook_event.noun, hook_event.label, hook.name(),
                       e.__class__.__name__, str(e)))
            except RezError:
                debug_print("Error in %s hook '%s': %s:\n%s"
                            % (hook_event.label, hook.name(),
                               e.__class__.__name__, str(e)))

    def get_previous_release(self):
        release_path = self.package.config.release_packages_path
        it = iter_packages(self.package.name, paths=[release_path])
        packages = sorted(it, key=lambda x: x.version, reverse=True)

        for package in packages:
            if package.version < self.package.version:
                return package
        return None

    def get_changelog(self):
        previous_package = self.get_previous_release()
        if previous_package:
            previous_revision = previous_package.revision
        else:
            previous_revision = None

        changelog = None
        with self.repo_operation():
            changelog = self.vcs.get_changelog(
                previous_revision,
                max_revisions=config.max_package_changelog_revisions)

        return changelog

    def get_release_data(self):
        """Get release data for this release.

        Returns:
            dict.
        """
        previous_package = self.get_previous_release()
        if previous_package:
            previous_version = previous_package.version
            previous_revision = previous_package.revision
        else:
            previous_version = None
            previous_revision = None

        if self.vcs is None:
            return dict(vcs="None",
                        previous_version=previous_version)

        revision = None
        with self.repo_operation():
            revision = self.vcs.get_current_revision()

        changelog = self.get_changelog()

        # truncate changelog - very large changelogs can cause package load
        # times to be very high, we don't want that
        maxlen = config.max_package_changelog_chars
        if maxlen and changelog and len(changelog) > maxlen + 3:
            changelog = changelog[:maxlen] + "..."

        return dict(vcs=self.vcs.name(),
                    revision=revision,
                    changelog=changelog,
                    previous_version=previous_version,
                    previous_revision=previous_revision)

    def _print(self, txt, *nargs):
        if self.verbose:
            if nargs:
                txt = txt % nargs
            print(txt)

    def _print_header(self, txt, n=1):
        if self.quiet:
            return

        self._print('')
        if n <= 1:
            br = '=' * 80
            title = "%s\n%s\n%s" % (br, txt, br)
        else:
            title = "%s\n%s" % (txt, '-' * len(txt))

        pr = Printer(sys.stdout)
        pr(title, heading)

    def _n_of_m(self, variant):
        num_variants = max(self.package.num_variants, 1)
        index = (variant.index or 0) + 1
        return "%d/%d" % (index, num_variants)


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
