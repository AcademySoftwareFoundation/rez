from rez.exceptions import RezError, ReleaseError
from rez.packages import Package, iter_packages
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.util import encode_filesystem_name
from rez.release_hook import create_release_hooks
from rez.vendor.version.version import Version
from rez.vendor import yaml
import getpass
import shutil
import os
import os.path
import sys
import time


# TODO convert to use Package/Variant rather than metadata directly

class BuildProcess(object):
    """A BuildProcess builds and possibly releases a package.

    A build process iterates over the variants of a package, creates the correct
    build environment for each variant, builds that variant using a build system
    (or possibly creates a script so the user can do that independently), and
    then possibly releases the package with the nominated VCS. This is an
    abstract base class, you should use a BuildProcess subclass.
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
        self.buildsys = buildsys

        if vcs and (vcs.path != working_dir):
            raise RezError("BuildProcess was provided with mismatched VCS")

        self.package = Package(working_dir)
        hook_names = self.package.settings.release_hooks or []
        self.hooks = create_release_hooks(hook_names, working_dir)

    def build(self, install_path=None, clean=False, install=False, variants=None):
        """Perform the build process.

        Iterates over the package's variants, resolves the environment for each,
        and runs the build system within each resolved environment.

        Args:
            install_path: The path to install the package to, if installing.
                Note that the actual path for the package install becomes
                {install_path}/{pkg_name}/{pkg_version}. If None, defaults
                to the local packages path setting.
            clean: If True, clear any previous build first. Otherwise, rebuild
                over the top of a previous build.
            install: If True, install the build.

        Returns:
            True if the build completed, False otherwise.
        """
        raise NotImplementedError

    def release(self):
        """Perform the release process.

        Returns:
            True if the release completed, False otherwise.
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
        super(StandardBuildProcess,self).__init__(working_dir=working_dir,
                                                  buildsys=buildsys,
                                                  vcs=vcs,
                                                  release_message=release_message,
                                                  ensure_latest=ensure_latest,
                                                  verbose=verbose)

    def _build(self, install_path, build_path, clean=False, install=False, variants=None):
        """Build all the variants of the package.

        Args:
            install_path: The path to install the package to, if installing.
                Note that the actual path for the package install becomes
                {install_path}/{pkg_name}/{pkg_version}. If None, defaults
                to the local packages path setting.
            build_path: The directory to build into.
            clean: If True, clear any previous build first. Otherwise, rebuild
                over the top of a previous build.
            install: If True, install the build.

        Returns:
            True if the build completed, False otherwise.
        """
        raise NotImplementedError

    def build(self, install_path=None, clean=False, install=False, variants=None):
        self._hdr("Building %s..." % self.package.qualified_name)

        base_build_path = os.path.join(self.working_dir,
                                       self.package.settings.build_directory)
        base_build_path = os.path.realpath(base_build_path)
        install_path = install_path or self.package.settings.local_packages_path

        return self._build(install_path=install_path,
                           build_path=base_build_path,
                           install=install,
                           clean=clean, variants=variants)

    def release(self):
        assert(self.vcs)
        install_path = self.package.settings.release_packages_path
        base_build_path = os.path.join(self.working_dir,
                                       self.package.settings.build_directory,
                                       "release")

        # load installed family config if present
        fam_info = None
        fam_yaml = os.path.join(install_path, self.package.name, "family.yaml")
        if os.path.isfile(fam_yaml):
            with open(fam_yaml) as f:
                fam_info = yaml.load(f.read())

        # check for package name conflict
        if fam_info is not None and "uuid" in fam_info:
            this_uuid = self.package.metadata.get("uuid")
            if this_uuid != fam_info["uuid"]:
                raise ReleaseError(("cannot release - '%s' is already " + \
                    "installed but appears to be a different package.") \
                    % self.package.qualified_name)

        # get last release, this stops same/earlier version release
        last_pkg,last_release_info = \
            self._get_last_release(install_path)

        print "Checking state of repository..."
        self.vcs.validate_repostate()

        last_ver = str(last_pkg.version) if last_pkg else None
        last_rev = (last_release_info or {}).get("revision")
        release_path = self._get_base_install_path(install_path)
        curr_rev = self.vcs.get_current_revision()
        changelog = self.vcs.get_changelog(last_rev)

        # run pre-release hooks
        for hook in self.hooks:
            self._prd("Running pre-release hook '%s'..." % hook.name())
            if not hook.pre_release(user=getpass.getuser(),
                                    install_path=release_path,
                                    release_message=self.release_message,
                                    changelog=changelog,
                                    previous_version=last_ver,
                                    previous_revision=last_rev):
                self._prd("Release cancelled by pre-release hook '%s'" % hook.name())
                return False

        # do the initial build
        self._hdr("Building...")
        if not self._build(install_path=install_path,
                           build_path=base_build_path,
                           install=False,
                           clean=True):
            return False

        # do a second build, installing to the release path
        self._hdr("Releasing...")
        if not self._build(install_path=install_path,
                           build_path=base_build_path,
                           install=True,
                           clean=False):
            return False

        # write family config file if not present
        if fam_info is None:
            fam_info = dict(
                uuid=self.package.metadata.get("uuid"))

            fam_content = yaml.dump(fam_info, default_flow_style=False)
            with open(fam_yaml, 'w') as f:
                f.write(fam_content)

        # write release info (changelog etc) into release path
        release_info = dict(
            timestamp=int(time.time()),
            vcs=self.vcs.name(),
            revision=curr_rev,
            changelog=changelog,
            release_message=self.release_message,
            previous_version=last_ver,
            previous_revision=last_rev)

        if self.release_message:
            msg = [x.rstrip() for x in self.release_message.strip().split('\n')]
            release_info["release_message"] = msg

        release_content = yaml.dump(release_info, default_flow_style=False)
        with open(os.path.join(release_path, "release.yaml"), 'w') as f:
            f.write(release_content)

        # write a tag for the new release into the vcs
        self.vcs.create_release_tag(self.release_message)

        # run post-release hooks
        for hook in self.hooks:
            self._prd("Running post-release hook '%s'..." % hook.name())
            hook.post_release(user=getpass.getuser(),
                              install_path=release_path,
                              release_message=self.release_message,
                              changelog=changelog,
                              previous_version=last_ver,
                              previous_revision=last_rev)

        print "\nPackage %s was released successfully.\n" \
            % self.package.qualified_name
        return True

    def _pr(self, s):
        if self.verbose:
            print s

    def _prd(self, s):
        if self.package.settings.debug("package_release"):
            print s

    def _hdr(self, s, h=1):
        self._pr('')
        if h <= 1:
            self._pr('-'*80)
            self._pr(s)
            self._pr('-'*80)
        else:
            self._pr(s)
            self._pr('-' * len(s))

    def _get_base_install_path(self, path):
        p = os.path.join(path, self.package.name)
        if self.package.version:
            p = os.path.join(p, str(self.package.version))
        return p

    def _get_last_release(self, release_path):
        for pkg in iter_packages(self.package.name, paths=[release_path],
                                 descending=True):
            if pkg.version == self.package.version:
                raise ReleaseError(("cannot release - an equal package "
                                   "version already exists: %s") % pkg.metafile)
            elif pkg.version > self.package.version:
                if self.ensure_latest:
                    raise ReleaseError(("cannot release - a newer package "
                                       "version already exists: %s") % pkg.metafile)
            else:
                release_yaml = os.path.join(pkg.base, "release.yaml")
                try:
                    with open(release_yaml) as f:
                        release_info = yaml.load(f.read())
                    return pkg, release_info
                except:
                    pass

        return (None,None)



class LocalSequentialBuildProcess(StandardBuildProcess):
    """A BuildProcess that sequentially builds the variants of the current
    package, on the local host.
    """
    def _build(self, install_path, build_path, clean=False, install=False, variants=None):
        base_install_path = self._get_base_install_path(install_path)
        nvariants = max(self.package.num_variants, 1)
        build_env_scripts = []
        timestamp = int(time.time())

        # iterate over variants
        for i, variant in enumerate(self.package.iter_variants()):
            if variants and i not in variants:
                self._hdr("Skipping %d/%d..." % (i+1, nvariants), 2)
                continue

            self._hdr("Building %d/%d..." % (i+1, nvariants), 2)
            subdir = variant.subpath

            # create build dir, possibly deleting previous build
            build_subdir = os.path.join(build_path, variant.subpath)
            install_path = os.path.join(base_install_path, variant.subpath)

            if clean and os.path.exists(build_subdir):
                shutil.rmtree(build_subdir)

            if not os.path.exists(build_subdir):
                os.makedirs(build_subdir)

            # resolve build environment and save to file
            rxt_path = os.path.join(build_subdir, "build.rxt")
            if os.path.exists(rxt_path):
                self._pr("Loading existing environment context...")
                r = ResolvedContext.load(rxt_path)
            else:
                request = variant.requires(build_requires=True,
                                           private_build_requires=True)

                self._pr("Resolving build environment: %s"
                         % ' '.join(str(x) for x in request))

                r = ResolvedContext(request,
                                    timestamp=timestamp,
                                    building=True)
                r.print_info()
                r.save(rxt_path)

            if r.status != "solved":
                print >> sys.stderr, \
                    "The build environment could not be resolved:\n%s" \
                    % r.failure_description
                return False

            # run build system
            self._pr("\nInvoking build system...")
            ret = self.buildsys.build(r,
                                      build_path=build_subdir,
                                      install_path=install_path,
                                      install=install)
            if ret.get("success"):
                script = ret.get("build_env_script")
                if script:
                    build_env_scripts.append(script)

                extra_files = ret.get("extra_files", []) + [rxt_path]
                if install and extra_files:
                    if not os.path.exists(install_path):
                        os.makedirs(install_path)
                    for file in extra_files:
                        shutil.copy(file, install_path)
            else:
                return False

        # write package definition file into release path
        if install:
            if not os.path.exists(base_install_path):
                os.makedirs(base_install_path)
            shutil.copy(self.package.metafile, base_install_path)

        if build_env_scripts:
            self._pr("\nThe following executable script(s) have been created:")
            self._pr('\n'.join(build_env_scripts))
            self._pr('')
        else:
            self._pr("\nAll %d build(s) were successful.\n" % nvariants)
        return True
