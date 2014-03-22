from rez.exceptions import RezError, ReleaseError
from rez.resources import load_package_metadata, load_package_settings
from rez.packages import iter_packages_in_range
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.util import encode_filesystem_name
from rez.release_hook import create_release_hooks
from rez.versions import ExactVersion
import getpass
import yaml
import shutil
import os
import os.path
import sys
import time



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

        self.metadata,self.metafile = load_package_metadata(working_dir)
        self.settings = load_package_settings(self.metadata)
        self.pkg_name = self.metadata["name"]

        hook_names = self.settings.release_hooks or []
        self.hooks = create_release_hooks(hook_names, working_dir)

    def build(self, install_path=None, clean=False, install=False):
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
    def _build(self, install_path, build_path, clean=False, install=False):
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

    def build(self, install_path=None, clean=False, install=False):
        self._hdr("Building...")
        base_build_path = os.path.join(self.working_dir,
                                       self.settings.build_directory)
        base_build_path = os.path.realpath(base_build_path)
        install_path = install_path or self.settings.local_packages_path

        return self._build(install_path=install_path,
                           build_path=base_build_path,
                           install=install,
                           clean=clean)

    def release(self):
        assert(self.vcs)
        pkg_str = self._pkg_str()
        install_path = self.settings.release_packages_path
        base_build_path = os.path.join(self.working_dir,
                                       self.settings.build_directory,
                                       "release")

        # load installed family config if present
        fam_info = None
        fam_yaml = os.path.join(install_path, self.pkg_name, "family.yaml")
        if os.path.isfile(fam_yaml):
            with open(fam_yaml) as f:
                fam_info = yaml.load(f.read())

        # check for package name conflict
        if fam_info is not None and "uuid" in fam_info:
            this_uuid = self.metadata.get("uuid")
            if this_uuid != fam_info["uuid"]:
                raise ReleaseError(("cannot release - '%s' is already " + \
                    "installed but appears to be a different package.") \
                    % self.pkg_name)

        # get last release, this will stop same/earlier version release
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
            if not hook.pre_release(package=pkg_str,
                                    user=getpass.getuser(),
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

        # write package definition file into release path
        shutil.copy(self.metafile, release_path)

        # write family config file if not present
        if fam_info is None:
            fam_info = dict(
                uuid=self.metadata.get("uuid"))

            fam_content = yaml.dump(fam_info, default_flow_style=False)
            with open(fam_yaml, 'w') as f:
                f.write(fam_content)

        # write release info (changelog etc) into release path
        release_info = dict(
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
            hook.post_release(package=pkg_str,
                              user=getpass.getuser(),
                              install_path=release_path,
                              release_message=self.release_message,
                              changelog=changelog,
                              previous_version=last_ver,
                              previous_revision=last_rev)

        print "\nPackage %s was released successfully.\n" % pkg_str
        return True

    def _pr(self, s):
        if self.verbose:
            print s

    def _prd(self, s):
        if self.settings.debug_package_release:
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

    def _pkg_str(self):
        s = self.pkg_name
        ver = self.metadata.get("version")
        if ver is not None:
            s += "-%s" % ver
        return s

    def _get_base_install_path(self, path):
        p = os.path.join(path, self.pkg_name)
        ver = self.metadata.get("version")
        if ver is not None:
            p = os.path.join(p, str(ver))
        return p

    def _get_build_list(self):
        builds = []
        requires = self.metadata.get('build_requires', []) + \
                   self.metadata.get('requires', [])
        variants = self.metadata.get('variants', [])

        if variants:
            for i,variant in enumerate(variants):
                dirs = [encode_filesystem_name(x) for x in variant]
                build = dict(variant_index=i,
                             subdir=os.path.join(*dirs),
                             requires=requires + variant)
                builds.append(build)
        else:
            build = dict(variant_index=None,
                         subdir="",
                         requires=requires)
            builds.append(build)
        return builds

    def _get_last_release(self, release_path):
        ver = ExactVersion(self.metadata.get("version", ''))

        for pkg in iter_packages_in_range(self.pkg_name,
                                          paths=[release_path]):
            if pkg.version == ver:
                raise ReleaseError(("cannot release - an equal package "
                                   "version already exists: %s") % pkg.metafile)
            elif pkg.version > ver:
                if self.ensure_latest:
                    raise ReleaseError(("cannot release - a newer package "
                                       "version already exists: %s") % pkg.metafile)
            else:
                path = os.path.dirname(pkg.metafile)
                release_yaml = os.path.join(path, "release.yaml")
                with open(release_yaml) as f:
                    release_info = yaml.load(f.read())
                return pkg, release_info

        return (None,None)



class LocalSequentialBuildProcess(StandardBuildProcess):
    """A BuildProcess that sequentially builds the variants of the current
    package, on the local host.
    """
    def _build(self, install_path, build_path, clean=False, install=False):
        base_install_path = self._get_base_install_path(install_path)

        build_env_scripts = []
        builds = self._get_build_list()

        # iterate over variants
        for i,bld in enumerate(builds):
            self._hdr("Building %d/%d..." % (i+1, len(builds)), 2)

            # create build dir, possibly deleting previous build
            build_subdir = os.path.join(build_path, bld["subdir"])
            install_path = os.path.join(base_install_path, bld["subdir"])

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
                request = bld["requires"]
                self._pr("Resolving build environment: %s" % ' '.join(request))
                r = ResolvedContext(request,
                                    timestamp=int(time.time()),
                                    build_requires=True)
                r.print_info()
                r.save(rxt_path)

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
                    for file in extra_files:
                        shutil.copy(file, install_path)
            else:
                return False

        if build_env_scripts:
            self._pr("\nThe following executable script(s) have been created:")
            self._pr('\n'.join(build_env_scripts))
            self._pr('')
        else:
            self._pr("\nAll %d build(s) were successful.\n" % len(builds))
        return True
