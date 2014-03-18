from rez.exceptions import RezError
from rez.resources import load_package_metadata, load_package_settings
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.util import encode_filesystem_name
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
    def __init__(self, working_dir, buildsys, vcs=None, verbose=True):
        """Create a BuildProcess.

        Args:
            working_dir: Directory containing the package to build.
            buildsys: Build system (a BuildSystem object) used to build the
                package.
            vcs: Version control system (a ReleaseVCS object) to use for the
                release process. If None, the package will only be built, not
                released.
        """
        self.verbose = verbose
        self.working_dir = working_dir
        self.buildsys = buildsys
        self.vcs = vcs

        self.metadata = load_package_metadata(working_dir)
        self.settings = load_package_settings(self.metadata)
        self.buildsys = buildsys

        if vcs and (vcs.path != working_dir):
            raise RezError("BuildProcess was provided with mismatched VCS")

    def build(self, install_path=None, clean=False):
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
        """
        raise NotImplementedError

    def release(self, install_path=None):
        """Perform the release process.

        Args:
            install_path: The path to install the package to. Note that the
                actual path for the package install becomes
                {install_path}/{pkg_name}/{pkg_version}. If None, defaults
                to the release packages path setting.
        """
        raise NotImplementedError

    def _pr(self, s):
        if self.verbose:
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
        p = os.path.join(path, self.metadata["name"])
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
                             subdir=os.path.join(dirs),
                             requires=requires + variant)
                builds.append(build)
        else:
            build = dict(variant_index=None,
                         subdir="",
                         requires=requires)
            builds.append(build)
        return builds



class LocalSequentialBuildProcess(BuildProcess):
    """A BuildProcess that sequentially builds the variants of the current
    package, on the local host.
    """
    def __init__(self, working_dir, buildsys, vcs=None, verbose=True):
        super(LocalSequentialBuildProcess,self).__init__(working_dir,
                                                         buildsys,
                                                         vcs=vcs,
                                                         verbose=verbose)

    def build(self, install_path=None, clean=False):
        base_build_path = os.path.join(self.working_dir,
                                       self.settings.build_directory)
        base_build_path = os.path.realpath(base_build_path)

        install_path = install_path or self.settings.local_packages_path
        base_install_path = self._get_base_install_path(install_path)

        build_env_scripts = []
        builds = self._get_build_list()
        self._hdr("Performing %d builds..." % len(builds))

        # iterate over variants
        for i,bld in enumerate(builds):
            self._hdr("Building %d/%d..." % (i+1, len(builds)), 2)

            # create build dir, possibly deleting previous build
            build_path = os.path.join(base_build_path, bld["subdir"])
            install_path = os.path.join(base_install_path, bld["subdir"])

            if clean and os.path.exists(build_path):
                shutil.rmtree(build_path)

            if not os.path.exists(build_path):
                os.makedirs(build_path)

            # resolve build environment and save to file
            rxt_path = os.path.join(build_path, "build.rxt")
            if os.path.exists(rxt_path):
                self._pr("Loading existing context...")
                r = ResolvedContext.load(rxt_path)
            else:
                request = bld["requires"]
                self._pr("Resolving build environment: %s" % ' '.join(request))
                r = ResolvedContext(request,
                                    timestamp=int(time.time()),
                                    build_requires=True)
                r.save(rxt_path)

            # run build system
            self._pr("Invoking build system...")
            ret = self.buildsys.build(r,
                                      build_path=build_path,
                                      install_path=install_path)
            if ret:
                if isinstance(ret, basestring):
                    script = ret
                    assert(os.path.isfile(script))
                    build_env_scripts.append(script)
            else:
                return False

        if build_env_scripts:
            child_sys = self.buildsys.child_build_system()
            assert(child_sys)
            assert(not build_child)
            self._pr("\nThe following executable script(s) have been created:")
            self._pr('\n'.join(build_env_scripts))
            self._pr(("\nExecuting one of these scripts will place you into a "
                     "build environment, where you can directly perform the "
                     "%s build step yourself.\n") % child_sys)
        else:
            self._pr("\nAll %d build(s) were successful.\n" % len(builds))
        return True

    def release(self, install_path=None):
        self._hdr("Releasing...")
        install_path = install_path or self.settings.release_packages_path
        base_install_path = self._get_base_install_path(install_path)

        # find last release of this pkg, make sure it's not >= this version
