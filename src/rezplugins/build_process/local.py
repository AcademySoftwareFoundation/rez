"""
Builds packages on local host
"""
from rez.config import config
from rez.package_repository import package_repository_manager
from rez.build_process import BuildProcessHelper, BuildType
from rez.release_hook import ReleaseHookEvent
from rez.exceptions import BuildError, PackageTestError
from rez.utils import with_noop
from rez.utils.logging_ import print_warning
from rez.utils.base26 import create_unique_base26_symlink
from rez.utils.colorize import Printer, warning
from rez.utils.filesystem import safe_makedirs, copy_or_replace, \
    make_path_writable, get_existing_path, forceful_rmtree
from rez.utils.sourcecode import IncludeModuleManager
from rez.utils.filesystem import TempDirs
from rez.package_test import PackageTestRunner, PackageTestResults

from hashlib import sha1
import json
import shutil
import os
import os.path


class LocalBuildProcess(BuildProcessHelper):
    """The default build process.

    This process builds a package's variants sequentially and on localhost.
    """

    # see `self._run_tests`
    tmpdir_manager = TempDirs(config.tmpdir, prefix="rez_testing_repo_")

    @classmethod
    def name(cls):
        return "local"

    def __init__(self, *nargs, **kwargs):
        super(LocalBuildProcess, self).__init__(*nargs, **kwargs)
        self.ran_test_names = set()
        self.all_test_results = PackageTestResults()

    def build(self, install_path=None, clean=False, install=False, variants=None):
        self._print_header("Building %s..." % self.package.qualified_name)

        # build variants
        num_visited, build_env_scripts = self.visit_variants(
            self._build_variant,
            variants=variants,
            install_path=install_path,
            clean=clean,
            install=install)

        self._print_header("Build Summary")

        self._print("\nAll %d build(s) were successful.\n", num_visited)

        if None not in build_env_scripts:
            self._print("\nThe following executable script(s) have been created:")
            self._print('\n'.join(build_env_scripts))
            self._print('')

        if self.all_test_results.num_tests:
            self.all_test_results.print_summary()
            print('')

        return num_visited

    def release(self, release_message=None, variants=None):
        self._print_header("Releasing %s..." % self.package.qualified_name)

        # test that we're in a state to release
        self.pre_release()

        release_path = self.package.config.release_packages_path
        release_data = self.get_release_data()
        changelog = release_data.get("changelog")
        previous_version = release_data.get("previous_version")
        previous_revision = release_data.get("previous_revision")

        # run pre-release hooks
        self.run_hooks(ReleaseHookEvent.pre_release,
                       install_path=release_path,
                       variants=variants,
                       release_message=release_message,
                       changelog=changelog,
                       previous_version=previous_version,
                       previous_revision=previous_revision)

        # release variants
        num_visited, released_variants = self.visit_variants(
            self._release_variant,
            variants=variants,
            release_message=release_message)

        # ignore skipped variants
        released_variants = [x for x in released_variants if x is not None]
        num_released = len(released_variants)

        # run post-release hooks
        self.run_hooks(ReleaseHookEvent.post_release,
                       install_path=release_path,
                       variants=released_variants,
                       release_message=release_message,
                       changelog=changelog,
                       previous_version=previous_version,
                       previous_revision=previous_revision)

        # perform post-release actions: tag repo etc
        if released_variants:
            self.post_release(release_message=release_message)

        self._print_header("Release Summary")

        msg = "\n%d of %d releases were successful" % (num_released, num_visited)
        if num_released < num_visited:
            Printer()(msg, warning)
        else:
            self._print(msg)

        if self.all_test_results.num_tests:
            print('')
            self.all_test_results.print_summary()
            print('')

        return num_released

    def _build_variant_base(self, variant, build_type, install_path=None,
                            clean=False, install=False, **kwargs):
        # create build/install paths
        install_path = install_path or self.package.config.local_packages_path
        package_install_path = self.get_package_install_path(install_path)
        variant_build_path = self.build_path

        if variant.index is None:
            variant_install_path = package_install_path
        else:
            subpath = variant._non_shortlinked_subpath
            variant_build_path = os.path.join(variant_build_path, subpath)
            variant_install_path = os.path.join(package_install_path, subpath)

        # create directories (build, install)
        if clean and os.path.exists(variant_build_path):
            self._rmtree(variant_build_path)

        safe_makedirs(variant_build_path)

        # find last dir of installation path that exists, and possibly make it
        # writable during variant installation
        #
        last_dir = get_existing_path(variant_install_path,
                                     topmost_path=install_path)

        if last_dir and config.make_package_temporarily_writable:
            ctxt = make_path_writable(last_dir)
        else:
            ctxt = with_noop()

        with ctxt:
            if install:
                # inform package repo that a variant is about to be built/installed
                pkg_repo = package_repository_manager.get_repository(install_path)
                pkg_repo.pre_variant_install(variant.resource)

                if not os.path.exists(variant_install_path):
                    safe_makedirs(variant_install_path)

                # if hashed variants are enabled, create the variant shortlink
                if variant.parent.hashed_variants:
                    try:
                        # create the dir containing all shortlinks
                        base_shortlinks_path = os.path.join(
                            package_install_path,
                            variant.parent.config.variant_shortlinks_dirname
                        )

                        safe_makedirs(base_shortlinks_path)

                        # create the shortlink
                        rel_variant_path = os.path.relpath(
                            variant_install_path, base_shortlinks_path)
                        create_unique_base26_symlink(
                            base_shortlinks_path, rel_variant_path)

                    except Exception as e:
                        # Treat any error as warning - lack of shortlink is not
                        # a breaking issue, it just means the variant root path
                        # will be long.
                        #
                        print_warning(
                            "Error creating variant shortlink for %s: %s: %s",
                            variant_install_path, e.__class__.__name__, e
                        )

            # Re-evaluate the variant, so that variables such as 'building' and
            # 'build_variant_index' are set, and any early-bound package attribs
            # are re-evaluated wrt these vars. This is done so that attribs such as
            # 'requires' can change depending on whether a build is occurring or not.
            #
            # Note that this re-evaluated variant is ONLY used here, for the purposes
            # of creating the build context. The variant that is actually installed
            # is the one evaluated where 'building' is False.
            #
            re_evaluated_package = variant.parent.get_reevaluated({
                "building": True,
                "build_variant_index": variant.index or 0,
                "build_variant_requires": variant.variant_requires
            })
            re_evaluated_variant = re_evaluated_package.get_variant(variant.index)

            # create build environment (also creates build.rxt file)
            context, rxt_filepath = self.create_build_context(
                variant=re_evaluated_variant,
                build_type=build_type,
                build_path=variant_build_path)

            # list of extra files (build.rxt etc) that are installed if an
            # installation is taking place
            #
            extra_install_files = [rxt_filepath]

            # create variant.json file. This identifies which variant this is.
            # This is important for hashed variants, where it is not obvious
            # which variant is in which root path. The file is there for
            # debugging purposes only.
            #
            if variant.index is not None:
                data = {
                    "index": variant.index,
                    "data": variant.parent.data["variants"][variant.index]
                }

                filepath = os.path.join(variant_build_path, "variant.json")
                extra_install_files.append(filepath)

                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)

            # run build system
            build_system_name = self.build_system.name()
            self._print("\nInvoking %s build system...", build_system_name)

            build_result = self.build_system.build(
                context=context,
                variant=variant,
                build_path=variant_build_path,
                install_path=variant_install_path,
                install=install,
                build_type=build_type)

            if not build_result.get("success"):
                # delete the possibly partially installed variant payload
                if install:
                    self._rmtree(variant_install_path)

                raise BuildError("The %s build system failed." % build_system_name)

            if install:
                # add some installation details to build result
                build_result.update({
                    "package_install_path": package_install_path,
                    "variant_install_path": variant_install_path
                })

                # the build system can also specify extra files that need to
                # be installed
                filepaths = build_result.get("extra_files")
                if filepaths:
                    extra_install_files.extend(filepaths)

                # install extra files
                for file_ in extra_install_files:
                    copy_or_replace(file_, variant_install_path)

                # Install include modules. Note that this doesn't need to be done
                # multiple times, but for subsequent variants it has no effect.
                #
                self._install_include_modules(install_path)

            return build_result

    def _install_include_modules(self, install_path):
        # install 'include' sourcefiles, used by funcs decorated with @include
        if not self.package.includes:
            return

        install_path = install_path or self.package.config.local_packages_path
        base_path = self.get_package_install_path(install_path)

        path = os.path.join(base_path, IncludeModuleManager.include_modules_subpath)
        safe_makedirs(path)

        definition_python_path = self.package.config.package_definition_python_path

        for name in self.package.includes:
            filepath = os.path.join(definition_python_path, name) + ".py"

            with open(filepath, "rb") as f:
                txt = f.read().strip()
            uuid = sha1(txt).hexdigest()

            dest_filepath = os.path.join(path, "%s.py" % name)
            shutil.copy(filepath, dest_filepath)  # overwrite if exists

            sha1_filepath = os.path.join(path, "%s.sha1" % name)
            with open(sha1_filepath, "w") as f:  # overwrite if exists
                f.write(uuid)

    def _rmtree(self, path):
        try:
            forceful_rmtree(path)
        except Exception as e:
            print_warning("Failed to delete %s - %s", path, e)

    def _build_variant(self, variant, install_path=None, clean=False,
                       install=False, **kwargs):
        if variant.index is not None:
            self._print_header(
                "Building variant %s (%s)..."
                % (variant.index, self._n_of_m(variant)))

        # build and possibly install variant (ie the payload, not package.py)
        install_path = install_path or self.package.config.local_packages_path

        def cancel_variant_install():
            if install:
                pkg_repo = package_repository_manager.get_repository(install_path)
                pkg_repo.on_variant_install_cancelled(variant.resource)

        try:
            build_result = self._build_variant_base(
                build_type=BuildType.local,
                variant=variant,
                install_path=install_path,
                clean=clean,
                install=install)
        except BuildError:
            # indicate to repo that the variant install is cancelled
            cancel_variant_install()

            raise

        if install:
            # run any tests that are configured to run pre-install
            try:
                self._run_tests(
                    variant,
                    run_on=["pre_install"],
                    package_install_path=build_result["package_install_path"]
                )
            except PackageTestError:
                # delete the installed variant payload
                self._rmtree(build_result["variant_install_path"])

                # indicate to repo that the variant install is cancelled
                cancel_variant_install()

                raise

            # install variant into package repository (ie update target package.py)
            variant.install(install_path)

        return build_result.get("build_env_script")

    def _release_variant(self, variant, release_message=None, **kwargs):
        release_path = self.package.config.release_packages_path

        # test if variant has already been released
        variant_ = variant.install(release_path, dry_run=True)
        if variant_ is not None:
            print_warning(
                "Skipping %s: destination variant already exists (%r)",
                self._n_of_m(variant), variant_.uri
            )
            return None

        def cancel_variant_install():
            pkg_repo = package_repository_manager.get_repository(release_path)
            pkg_repo.on_variant_install_cancelled(variant.resource)

        if variant.index is not None:
            self._print_header("Releasing variant %s..." % self._n_of_m(variant))

        # build and install variant
        try:
            build_result = self._build_variant_base(
                build_type=BuildType.central,
                variant=variant,
                install_path=release_path,
                clean=True,
                install=True)
        except BuildError:
            # indicate to repo that the variant install is cancelled
            cancel_variant_install()

            raise

        # run any tests that are configured to run pre-install
        try:
            self._run_tests(
                variant,
                run_on=["pre_release"],
                package_install_path=build_result["package_install_path"]
            )
        except PackageTestError:
            # delete the installed variant payload
            self._rmtree(build_result["variant_install_path"])

            # indicate to repo that the variant install is cancelled
            cancel_variant_install()

            raise

        # add release info to variant, and install it into package repository
        release_data = self.get_release_data()
        release_data["release_message"] = release_message
        variant_ = variant.install(release_path, overrides=release_data)
        return variant_

    def _run_tests(self, variant, run_on, package_install_path):
        """Possibly run package tests on the given variant.

        During an install/release, the following steps occur:
        1. The variant's payload is installed, but package.py is not yet updated
           (see `self._build_variant_base`)
        2. The variant is installed on its own, into a temp package.py
        3. Tests are run on this temp variant, whose root is patched to point
           at the real variant payload installation
        4. On success, the rest of the release process goes ahead, and the real
           package.py is updated appropriately
        5. On failure, the release is aborted.
        """
        package = variant.parent

        # see if there are tests to run, noop if not
        test_names = PackageTestRunner.get_package_test_names(
            package=package,
            run_on=run_on,
            ran_once=self.ran_test_names
        )

        if not test_names:
            return

        testing_repo_path = self.tmpdir_manager.mkdtemp()

        # install the variant into the temp repo. This just creates the package.py.
        #
        # Note: the special attribute '_redirected_base' is supported by the
        # 'filesystem' package repo class, specifically for this case.
        #
        # Note: This adds the temp variant to the global resource cache, which is
        # not really what we want. This doesn't cause problems however. See
        # https://github.com/nerdvegas/rez/issues/809
        #
        variant.install(
            path=testing_repo_path,
            overrides={
                "_redirected_base": package_install_path
            }
        )

        # construct a packages path that guarantees the temp testing variant
        # will be used
        package_paths = [testing_repo_path] + config.packages_path

        # run the tests, and raise an exception if any fail. This will abort
        # the install/release
        runner = PackageTestRunner(
            package_request=variant.parent.as_exact_requirement(),
            package_paths=package_paths,
            cumulative_test_results=self.all_test_results,
            stop_on_fail=True,
            verbose=1
        )

        for test_name in test_names:
            if not runner.stopped_on_fail:
                runner.run_test(test_name)
                self.ran_test_names.add(test_name)

        if runner.num_tests:
            print('')
            runner.print_summary()

        if runner.num_failed:
            print('')
            raise PackageTestError(
                "%d tests failed; the installation has been cancelled"
                % runner.num_failed
            )


def register_plugin():
    return LocalBuildProcess


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
