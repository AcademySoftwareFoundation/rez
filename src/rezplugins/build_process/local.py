"""
Builds packages on local host
"""
from rez.package_repository import package_repository_manager
from rez.build_process_ import BuildProcessHelper, BuildType
from rez.release_hook import ReleaseHookEvent
from rez.exceptions import BuildError
from rez.utils import with_noop
from rez.utils.logging_ import print_warning
from rez.utils.base26 import create_unique_base26_symlink
from rez.utils.colorize import Printer, warning
from rez.utils.filesystem import safe_makedirs, copy_or_replace, \
    make_path_writable, get_existing_path
from rez.utils.sourcecode import IncludeModuleManager

from hashlib import sha1
import json
import shutil
import os
import os.path


class LocalBuildProcess(BuildProcessHelper):
    """The default build process.

    This process builds a package's variants sequentially and on localhost.
    """
    @classmethod
    def name(cls):
        return "local"

    def build(self, install_path=None, clean=False, install=False, variants=None):
        self._print_header("Building %s..." % self.package.qualified_name)

        # build variants
        num_visited, build_env_scripts = self.visit_variants(
            self._build_variant,
            variants=variants,
            install_path=install_path,
            clean=clean,
            install=install)

        if None not in build_env_scripts:
            self._print("\nThe following executable script(s) have been created:")
            self._print('\n'.join(build_env_scripts))
            self._print('')
        else:
            self._print("\nAll %d build(s) were successful.\n", num_visited)
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

        if self.verbose:
            msg = "\n%d of %d releases were successful" % (num_released, num_visited)
            if num_released < num_visited:
                Printer()(msg, warning)
            else:
                self._print(msg)

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
            shutil.rmtree(variant_build_path)

        safe_makedirs(variant_build_path)

        # find last dir of installation path that exists, and possibly make it
        # writable during variant installation
        #
        last_dir = get_existing_path(variant_install_path,
                                     topmost_path=install_path)
        if last_dir:
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

            # create build environment
            context, rxt_filepath = self.create_build_context(
                variant=re_evaluated_variant,
                build_type=build_type,
                build_path=variant_build_path)

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
                raise BuildError("The %s build system failed." % build_system_name)

            if install:
                # Install the 'variant.json' file, which identifies which variant
                # this is. This is important for hashed variants, where it is not
                # obvious which variant is in which root path. The file is there
                # for debugging purposes only.
                #
                if variant.index is not None:
                    data = {
                        "index": variant.index,
                        "data": variant.parent.data["variants"][variant.index]
                    }

                    filepath = os.path.join(variant_install_path, "variant.json")
                    with open(filepath, 'w') as f:
                        json.dump(data, f, indent=2)

                # install some files for debugging purposes (incl build.rxt)
                extra_files = build_result.get("extra_files", [])
                if rxt_filepath:
                    extra_files = extra_files + [rxt_filepath]

                for file_ in extra_files:
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
            dest_filepath = os.path.join(path, "%s-%s.py" % (name, uuid))

            if not os.path.exists(dest_filepath):
                shutil.copy(filepath, dest_filepath)

    def _build_variant(self, variant, install_path=None, clean=False,
                       install=False, **kwargs):
        if variant.index is not None:
            self._print_header(
                "Building variant %s (%s)..."
                % (variant.index, self._n_of_m(variant)))

        # build and possibly install variant
        install_path = install_path or self.package.config.local_packages_path
        build_result = self._build_variant_base(
            build_type=BuildType.local,
            variant=variant,
            install_path=install_path,
            clean=clean,
            install=install)

        # install variant into package repository
        if install:
            variant.install(install_path)

        return build_result.get("build_env_script")

    def _release_variant(self, variant, release_message=None, **kwargs):
        release_path = self.package.config.release_packages_path

        # test if variant has already been released
        variant_ = variant.install(release_path, dry_run=True)
        if variant_ is not None:
            self._print_header("Skipping %s: destination variant already exists (%r)"
                               % (self._n_of_m(variant), variant_.uri))
            return None

        if variant.index is not None:
            self._print_header("Releasing variant %s..." % self._n_of_m(variant))

        # build and install variant
        self._build_variant_base(
            build_type=BuildType.central,
            variant=variant,
            install_path=release_path,
            clean=True,
            install=True)

        # add release info to variant, and install it into package repository
        release_data = self.get_release_data()
        release_data["release_message"] = release_message
        variant_ = variant.install(release_path, overrides=release_data)
        return variant_


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
