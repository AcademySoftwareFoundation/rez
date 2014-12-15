from rez.packages import load_developer_package, iter_packages
from rez.exceptions import RezError, BuildError, BuildContextResolveError, \
    ReleaseError
from rez.resolver import ResolverStatus
from rez.resolved_context import ResolvedContext
from rez.util import convert_dicts, AttrDictWrapper, print_debug
from rez.release_hook import create_release_hooks
from rez.yaml import dump_yaml
from rez import __version__
from rez.vendor.enum import Enum
import getpass
import shutil
import os
import os.path
import time


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
    def __init__(self, working_dir, buildsys, vcs=None, release_message=None,
                 ensure_latest=True, verbose=True):
        """Create a BuildProcess.

        Args:
            working_dir: Directory containing the package to build.
            buildsys: Build system (a BuildSystem object) used to build the
                package.
            vcs: Version control system (a ReleaseVCS object) to use for the
                release process. If None, the package will only be built, not
                released.
            release_message: A message that will be stored on the release tag,
                if a release is performed.
            ensure_latest: If True, do not allow the release process to occur
                if an newer versioned package is already released.
        """
        self.verbose = verbose
        self.working_dir = working_dir
        self.buildsys = buildsys
        self.vcs = vcs
        self.release_message = release_message
        self.ensure_latest = ensure_latest

        if vcs and (vcs.path != working_dir):
            raise RezError("BuildProcess was provided with mismatched VCS")

        self.package = load_developer_package(working_dir)
        hook_names = self.package.config.release_hooks or []
        self.hooks = create_release_hooks(hook_names, working_dir)

    def build(self, install_path=None, clean=False, install=False,
              variants=None):
        """Perform the build process.

        Iterates over the package's variants, resolves the environment for
        each, and runs the build system within each resolved environment.

        Args:
            install_path: The path to install the package to, if installing.
                Note that the actual path for the package install becomes
                {install_path}/{pkg_name}/{pkg_version}. If None, defaults
                to the local packages path setting.
            clean: If True, clear any previous build first. Otherwise, rebuild
                over the top of a previous build.
            install: If True, install the build.

        Raises:
            BuildError: If the build failed.
        """
        raise NotImplementedError

    def release(self):
        """Perform the release process.

        Raises:
            ReleaseError: If the release failed.
        """
        raise NotImplementedError


class StandardBuildProcess(BuildProcess):
    """An abstract base class that defines some useful common functionality.

    You should implement the _build() method only. If you need more flexibility
    than this class offers, then either override the build() and release()
    methods as well, or subclass BuildProcess directly.
    """
    def __init__(self, working_dir, buildsys, vcs=None, release_message=None,
                 ensure_latest=True, verbose=True):
        super(StandardBuildProcess, self).__init__(
            working_dir=working_dir,
            buildsys=buildsys,
            vcs=vcs,
            release_message=release_message,
            ensure_latest=ensure_latest,
            verbose=verbose)

    def _build(self, install_path, build_path, clean=False, install=False,
               variants=None, build_type=BuildType.local):
        """Build all the variants of the package.

        Args:
            install_path (str): The path to install the package to, if installing.
                Note that the actual path for the package install becomes
                {install_path}/{pkg_name}/{pkg_version}. If None, defaults
                to the local packages path setting.
            build_path (str): The directory to build into.
            clean (bool): If True, clear any previous build first. Otherwise,
                rebuild over the top of a previous build.
            install (bool): If True, install the build.
            build_type (bool): The BuildType for the current build.

        Returns:
            True if the build completed, False otherwise.
        """
        raise NotImplementedError

    def build(self, install_path=None, clean=False, install=False,
              variants=None):
        self._hdr("Building %s..." % self.package.qualified_name)

        base_build_path = os.path.join(self.working_dir,
                                       self.package.config.build_directory)
        base_build_path = os.path.realpath(base_build_path)
        install_path = (install_path or
                        self.package.config.local_packages_path)

        self._build(install_path=install_path,
                    build_path=base_build_path,
                    install=install,
                    clean=clean,
                    variants=variants,
                    build_type=BuildType.local)

    def release(self):
        assert(self.vcs)
        install_path = self.package.config.release_packages_path
        base_build_path = os.path.join(self.working_dir,
                                       self.package.config.build_directory,
                                       "release")

        if not os.path.exists(install_path):
            raise ReleaseError("Release path does not exist: %r" % install_path)

        print "Checking state of repository..."
        self.vcs.validate_repostate()
        release_path = self._get_base_install_path(install_path)
        release_settings = self.package.config.plugins.release_vcs

        # format tag
        try:
            tag_name = self.package.format(release_settings.tag_name)
            if not tag_name:
                tag_name = "unversioned"
        except Exception as e:
            raise ReleaseError("Error formatting tag name for release: %s"
                               % str(e))

        # get last release, this stops same/earlier version release
        last_pkg = self._get_last_release(install_path)
        last_version = None
        last_revision = None
        if last_pkg:
            # check uuid against previous package
            if last_pkg.uuid and self.package.uuid \
                    and last_pkg.uuid != self.package.uuid:
                raise ReleaseError("cannot release - previous release %s appears "
                                   "to be a different package (UUID mismatch)"
                                   % str(last_pkg))

            # get previous version/revision, needed by hooks and vcs.get_changelog
            last_version = last_pkg.version
            last_revision = last_pkg.revision
            if isinstance(last_revision, AttrDictWrapper):
                last_revision = convert_dicts(last_pkg.revision,
                                              to_class=dict,
                                              from_class=AttrDictWrapper)

        revision = self.vcs.get_current_revision()
        changelog = self.vcs.get_changelog(last_revision)

        def _run_hooks(name, func_name, can_cancel):
            for hook in self.hooks:
                self._prd("Running %s hook '%s'..." % (name, hook.name()))
                error_class = ReleaseError if can_cancel else None
                try:
                    func = getattr(hook, func_name)
                    func(user=getpass.getuser(),
                         install_path=release_path,
                         release_message=self.release_message,
                         changelog=changelog,
                         previous_version=last_version,
                         previous_revision=last_revision)
                except error_class as e:
                    msg = ("Release cancelled by %s hook '%s':\n%s"
                           % (name, hook.name(), str(e)))
                    self._prd(msg)
                    raise ReleaseError(msg)

        # run pre-build hooks
        _run_hooks("pre-build", "pre_build", True)

        def _do_build(install, clean):
            try:
                self._build(install_path=install_path,
                            build_path=base_build_path,
                            install=install,
                            clean=clean,
                            build_type=BuildType.central)
            except BuildError as e:
                raise ReleaseError("The build failed: %s" % str(e))

        # do an initial clean build
        self._hdr("Building...")
        _do_build(install=False, clean=True)

        # run pre-release hooks
        _run_hooks("pre-release", "pre_release", True)

        # do a second non-clean build, installing to the release path
        self._hdr("Releasing %s..." % self.package.qualified_name)
        _do_build(install=True, clean=False)

        def _trim_changelog(changelog, maxsize):
            if maxsize == -1:
                return changelog

            lines = changelog.split("\n")
            return "\n".join(lines[:maxsize])

        # write release info (changelog etc) into release path
        changelog_maxsize = self.package.config.changelog_maxsize
        release_info = dict(
            timestamp=int(time.time()),
            revision=revision,
            changelog=_trim_changelog(changelog, changelog_maxsize))

        if self.release_message:
            release_message = self.release_message.strip()
        else:
            release_message = "Rez-%s released %s" \
                % (__version__, self.package.qualified_name)
        release_info["release_message"] = release_message

        if last_pkg:
            release_info["previous_version"] = str(last_version)
            release_info["previous_revision"] = last_revision

        release_content = dump_yaml(release_info)
        with open(os.path.join(release_path, "release.yaml"), 'w') as f:
            f.write(release_content)

        # write a tag for the new release into the vcs
        self.vcs.create_release_tag(tag_name=tag_name, message=release_message)

        # run post-release hooks
        _run_hooks("post-release", "post_release", False)

        print "\nPackage %s was released successfully.\n" \
            % self.package.qualified_name

    def _pr(self, s):
        if self.verbose:
            print s

    def _prd(self, s):
        if self.package.config.debug("package_release"):
            print_debug(s)

    def _hdr(self, s, h=1):
        self._pr('')
        if h <= 1:
            self._pr('-' * 80)
            self._pr(s)
            self._pr('-' * 80)
        else:
            self._pr(s)
            self._pr('-' * len(s))

    def _get_base_install_path(self, path):
        p = os.path.join(path, self.package.name)
        if self.package.version:
            p = os.path.join(p, str(self.package.version))
        return p

    def _get_last_release(self, release_path):
        it = iter_packages(self.package.name, paths=[release_path])
        packages = sorted(it, key=lambda x: x.version, reverse=True)
        for pkg in packages:
            if pkg.version == self.package.version:
                raise ReleaseError(("cannot release - an equal package "
                                    "version already exists: %s")
                                   % str(pkg))
            else:
                if pkg.version > self.package.version and self.ensure_latest:
                    raise ReleaseError(("cannot release - a newer package "
                                       "version already exists: %s")
                                       % str(pkg))
                return pkg
        return None


class LocalSequentialBuildProcess(StandardBuildProcess):
    """A BuildProcess that sequentially builds the variants of the current
    package, on the local host.
    """
    def _build(self, install_path, build_path, clean=False, install=False,
               variants=None, build_type=BuildType.local):
        base_install_path = self._get_base_install_path(install_path)
        build_env_scripts = []
        timestamp = int(time.time())

        num_built_variants = 0
        nvariants = max(self.package.num_variants, 1)
        if variants:
            present_variants = range(self.package.num_variants)
            invalid_variants = set(variants) - set(present_variants)
            if invalid_variants:
                raise BuildError(
                    "The following variants are not present: %s"
                    % ", ".join(str(x) for x in sorted(invalid_variants)))

        # iterate over variants
        for i, variant in enumerate(self.package.iter_variants()):
            if variants and i not in variants:
                self._hdr("Skipping %d/%d..." % (i + 1, nvariants), 2)
                continue

            self._hdr("Building %d/%d..." % (i + 1, nvariants), 2)

            # create build dir, possibly deleting previous build
            build_subdir = os.path.join(build_path, variant.subpath)
            install_path = os.path.join(base_install_path, variant.subpath)
            rxt_file = os.path.join(build_subdir, "build.rxt")

            if build_type == BuildType.local:
                packages_path = self.package.config.packages_path
            else:
                packages_path = self.package.config.nonlocal_packages_path

            if clean and os.path.exists(build_subdir):
                shutil.rmtree(build_subdir)

            if not os.path.exists(build_subdir):
                os.makedirs(build_subdir)

            # resolve build environment and save to file, possibly reusing
            # existing build context file
            r = None
            if os.path.exists(rxt_file) and os.path.getmtime(self.package.path) \
                    < os.path.getmtime(rxt_file):
                try:
                    r_ = ResolvedContext.load(rxt_file)
                    r_.validate()
                    if r_.success and (r_.package_paths == packages_path):
                        r = r_
                except:
                    pass

            if r is None:
                request = variant.get_requires(build_requires=True,
                                               private_build_requires=True)
                self._pr("Resolving build environment: %s"
                         % ' '.join(str(x) for x in request))
                r = ResolvedContext(request,
                                    package_paths=packages_path,
                                    timestamp=timestamp,
                                    building=True)
                r.save(rxt_file)

            r.print_info()
            if r.status != ResolverStatus.solved:
                raise BuildContextResolveError(r)

            # run build system
            self._pr("\nInvoking %s build system..." % self.buildsys.name())
            ret = self.buildsys.build(r,
                                      build_path=build_subdir,
                                      install_path=install_path,
                                      install=install,
                                      build_type=build_type)
            if ret.get("success"):
                num_built_variants += 1
                script = ret.get("build_env_script")
                if script:
                    build_env_scripts.append(script)

                extra_files = ret.get("extra_files", []) + [rxt_file]
                if install and extra_files:
                    if not os.path.exists(install_path):
                        os.makedirs(install_path)
                    for file in extra_files:
                        shutil.copy(file, install_path)
            else:
                raise BuildError("The %s build system failed"
                                 % self.buildsys.name())

        # write package definition file into release path
        # TODO this has to change to resource copying/merging
        if install:
            if not os.path.exists(base_install_path):
                os.makedirs(base_install_path)
            shutil.copy(self.package.path, base_install_path)

        if build_env_scripts:
            self._pr("\nThe following executable script(s) have been created:")
            self._pr('\n'.join(build_env_scripts))
            self._pr('')
        else:
            self._pr("\nAll %d build(s) were successful.\n"
                     % num_built_variants)
