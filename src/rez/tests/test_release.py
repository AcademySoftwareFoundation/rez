"""
test the release system
"""
from rez.build_process_ import create_build_process
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.release_vcs import create_release_vcs
from rez.packages_ import iter_packages
from rez.vendor import yaml
from rez.system import system
from rez.exceptions import BuildError, ReleaseError, ReleaseVCSError
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin, shell_dependent, \
    install_dependent, git_dependent, hg_dependent, svn_dependent
from rez.package_serialise import dump_package_data
from rez.serialise import FileFormat
import rez.bind.platform
import rez.bind.arch
import rez.bind.os
import rez.bind.python
import shutil
import os.path
import subprocess


class TestRelease(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.dirname(__file__)
        cls.src_origin_root = os.path.join(path, "data", "release")
        cls.src_root = os.path.join(cls.root, "src")
        cls.install_root = os.path.join(cls.root, "packages")

        cls.settings = dict(
            packages_path=[cls.install_root],
            package_filter=None,
            release_packages_path=cls.install_root,
            resolve_caching=False,
            warn_untimestamped=False,
            implicit_packages=[],
            plugins={'release_vcs': {'git': {'allow_no_upstream': True}}})

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @classmethod
    def _create_context(cls, *pkgs):
        return ResolvedContext(pkgs)

    def _setup_release(self, subdir, build_subdir=None):
        self.src_origin = os.path.join(self.src_origin_root, subdir)

        # start fresh
        system.clear_caches()
        if os.path.exists(self.install_root):
            shutil.rmtree(self.install_root)
        if os.path.exists(self.src_root):
            shutil.rmtree(self.src_root)
        shutil.copytree(self.src_origin, self.src_root)

        if build_subdir is None:
            self.build_dir = self.src_root
        else:
            self.build_dir = os.path.join(self.src_root, build_subdir)

        self.packagefile = os.path.join(self.build_dir, "package.yaml")
        with open(self.packagefile) as f:
            self.package_data = yaml.load(f.read())

        # create the build system
        self.buildsys = create_build_system(self.build_dir, verbose=True)
        self.assertEqual(self.buildsys.name(), "bez")

    def _write_package(self):
        with open(self.packagefile, 'w') as f:
            dump_package_data(self.package_data, f, format_=FileFormat.yaml)

    def _create_builder(self, ensure_latest=True):
        return create_build_process(process_type="local",
                                    working_dir=self.build_dir,
                                    build_system=self.buildsys,
                                    vcs=self.vcs,
                                    ensure_latest=ensure_latest,
                                    ignore_existing_tag=True,
                                    verbose=True)

    def assertVariantsEqual(self, vars1, vars2):
        """Utility function to compare string-variants with formal lists of
        "PackageRequest" objects
        """
        from rez.utils.formatting import PackageRequest

        def _standardize_variants(variants):
            return [list(str(req) for req in variant) for variant in variants]

        self.assertEqual(_standardize_variants(vars1),
                         _standardize_variants(vars2))

    @shell_dependent()
    @install_dependent
    def test_1(self):
        """Basic release."""
        # release should fail because release path does not exist
        self._setup_release("basic")

        # create the vcs - should error because stub file doesn't exist yet
        with self.assertRaises(ReleaseVCSError):
            create_release_vcs(self.build_dir)

        # make the stub file
        stubfile = os.path.join(self.build_dir, ".stub")
        with open(stubfile, 'w'):
            pass

        # create the vcs - should work now
        self.vcs = create_release_vcs(self.build_dir)
        self.assertEqual(self.vcs.name(), "stub")

        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # release should work this time
        os.mkdir(self.install_root)
        builder.release()

        # check a file to see the release made it
        filepath = os.path.join(self.install_root,
                                "foo", "1.0", "data", "data.txt")
        self.assertTrue(os.path.exists(filepath))

        # failed release (same version released again)
        builder = self._create_builder()
        num_variants = builder.release()
        self.assertEqual(num_variants, 0)

        # update package version and release again
        self.package_data["version"] = "1.1"
        self._write_package()
        builder = self._create_builder()
        builder.release()

        # change version to earlier and do failed release attempt
        self.package_data["version"] = "1.0.1"
        self._write_package()
        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # release again, this time allow not latest
        builder = self._create_builder(ensure_latest=False)
        builder.release()

        # change uuid and do failed release attempt
        self.package_data["version"] = "1.2"
        self.package_data["uuid"] += "_CHANGED"
        self._write_package()
        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # check the vcs contains the tags we expect
        expected_value = set(["foo-1.0", "foo-1.0.1", "foo-1.1"])
        with open(stubfile) as f:
            stub_data = yaml.load(f.read())
        tags = set(stub_data.get("tags", {}).keys())
        self.assertEqual(tags, expected_value)

        # check the package install path contains the packages we expect
        it = iter_packages("foo", paths=[self.install_root])
        qnames = set(x.qualified_name for x in it)
        self.assertEqual(qnames, expected_value)

    @shell_dependent()
    @install_dependent
    def test_2_variant_add(self):
        """Test variant installation on release
        """
        self._setup_release("variants")

        # make the stub file, set up the vcs
        stubfile = os.path.join(self.build_dir, ".stub")
        with open(stubfile, 'w'):
            pass
        self.vcs = create_release_vcs(self.build_dir)

        # copy the spangle package onto the packages path
        os.mkdir(self.install_root)
        shutil.copytree(os.path.join(self.build_dir, 'spangle'),
                        os.path.join(self.install_root, 'spangle'))

        # release the bar package, which has spangle-1.0 and 1.1 variants
        builder = self._create_builder()
        builder.release()

        # check that the released package has two variants, and the "old"
        # description...
        rel_packages = list(iter_packages("bar", paths=[self.install_root]))
        self.assertEqual(len(rel_packages), 1)
        rel_package = rel_packages[0]
        self.assertVariantsEqual(rel_package.variants, [['spangle-1.0'],
                                                        ['spangle-1.1']])
        self.assertEqual(rel_package.description,
                         'a package with two variants')

        # now, change the package so it has a single spangle-2.0 variant...
        self.package_data['variants'] = [['spangle-2.0']]
        new_desc = 'added spangle-2.0 variant'
        self.package_data['description'] = new_desc
        self._write_package()

        # ...then try to re-release
        builder = self._create_builder()
        builder.release()

        # check that the released package now three variants, and the "new"
        # description...
        rel_packages = list(iter_packages("bar", paths=[self.install_root]))
        self.assertEqual(len(rel_packages), 1)
        rel_package = rel_packages[0]
        self.assertVariantsEqual(rel_package.variants, [['spangle-1.0'],
                                                        ['spangle-1.1'],
                                                        ['spangle-2.0']])
        self.assertEqual(rel_package.description, new_desc)

        # finally, release a package that contains a variant already released,
        # but with a different index...
        self.package_data['variants'] = [['spangle-1.1']]
        third_desc = 'releasing with already existing variant'
        self.package_data['description'] = third_desc
        self._write_package()
        builder = self._create_builder()
        builder.release()

        # make sure that the variant indices stayed the same...
        rel_packages = list(iter_packages("bar", paths=[self.install_root]))
        self.assertEqual(len(rel_packages), 1)
        rel_package = rel_packages[0]
        self.assertVariantsEqual(rel_package.variants, [['spangle-1.0'],
                                                        ['spangle-1.1'],
                                                        ['spangle-2.0']])
        # ...but that the description was updated
        self.assertEqual(rel_package.description, third_desc)

    def _assert_package_file_in_repo(self, repo_type, env=None):
        self._setup_release("package_in_repo", build_subdir="foo")
        os.mkdir(self.install_root)

        # first, try without any repo - should fail
        with self.assertRaises(ReleaseVCSError):
            create_release_vcs(self.build_dir)

        def repo_cmd(*args):
            # make a repo at the src_root, not the build_dir, so we can
            # add "confusing" package.yaml - ie, if the current dir is
            # the build dir, the relative path "package.yaml" is the "real"
            # package.yaml - but relative to the repo root, it is the "fake"
            # one. This shouldn't trip up rez...
            if args and args[0] == 'commit' and repo_type == 'hg':
                args = args + ('--user', 'dummyuser')
            subprocess.check_call([repo_type] + list(args), env=env,
                                  cwd=self.src_root)

        if repo_type == 'svn':
            # for svn, we need a separate "server"/origin repo... luckily,
            # we can make it in a subdir of what will (eventually) be the
            # checkout... which is a bit confusing, but allows us to keep
            # everything under the src_root, which guarantees it will get
            # cleaned up properly the next time _setup_release is run...

            svn_repo_name = 'svn_server_repo'
            repo_data_dir = os.path.join(self.src_root, svn_repo_name)
            server_url = 'file://%s' % os.path.abspath(repo_data_dir)
            trunk_url = server_url + '/trunk'

            def _make_repo():
                subprocess.check_call(['svnadmin', 'create', svn_repo_name],
                                      env=env, cwd=self.src_root)
                # setup the trunk + tags, then remove them so they don't
                # clutter what will be our working dir...
                def make_root_repo_dir(dir_name):
                    path = os.path.join(self.src_root, dir_name)
                    dir_url = server_url + '/' + dir_name
                    os.mkdir(path)
                    repo_cmd('import', path, dir_url, '-m',
                             'adding %s root dir' % dir_name)
                    shutil.rmtree(path)

                make_root_repo_dir('trunk')
                make_root_repo_dir('tags')

                repo_cmd('checkout', trunk_url, self.src_root)

                # need to add foo dir, but don't use make_repo_root_dir, since
                # that will delete it after...
                repo_cmd('add', '--depth=empty', 'foo')
                repo_cmd('commit', '-m', 'added foo dir')

            def delete_repo():
                shutil.rmtree(repo_data_dir)
                shutil.rmtree(os.path.join(self.src_root, '.' + repo_type))

        else:
            # git and hg
            def _make_repo():
                repo_cmd('init')

            def delete_repo():
                shutil.rmtree(os.path.join(self.src_root, '.' + repo_type))

        def setup_repo():
            _make_repo()
            # add in the "deceptive" other package.yaml + rezbuild.py
            repo_cmd('add', 'package.yaml', 'rezbuild.py')
            repo_cmd('commit', '-m', 'initial commit with dummy files')

        setup_repo()

        # make the vcs... but release should fail, because we don't have the
        # required files in the repo...
        self.vcs = create_release_vcs(self.build_dir)
        self.assertEqual(self.vcs.name(), repo_type)
        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # now add in the real package.yaml - should still fail, because
        # it doesn't have rezbuild.py
        repo_cmd('add', 'foo/package.yaml')
        repo_cmd('commit', '-m', 'added foo/package.yaml')
        self.vcs = create_release_vcs(self.build_dir)
        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # back up , and this time add in only rezbuild.yaml... should fail,
        # because it doesn't have package.yaml...
        delete_repo()
        setup_repo()
        repo_cmd('add', 'foo/rezbuild.py')
        repo_cmd('commit', '-m', 'added foo/rezbuild.py')
        self.vcs = create_release_vcs(self.build_dir)
        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # now, make sure both are added... and it should work!
        repo_cmd('add', 'foo/package.yaml')
        repo_cmd('commit', '-m', 'added foo/package.yaml')
        self.vcs = create_release_vcs(self.build_dir)
        builder.release()

        # finally, change the package.yaml, and then try to release again...
        # it should fail due to uncommitted changes
        with open(os.path.join(self.build_dir, 'package.yaml'), 'a') as f:
            f.write('\n\n')

        self.vcs = create_release_vcs(self.build_dir)
        with self.assertRaises(ReleaseError):
            builder.release()

    @git_dependent
    def test_3_git_package_file_in_repo(self):
        """Test that if package.yaml not in git repo, release is not allowed
        """
        env = dict(os.environ)
        # disable user/system gitconfig loading...
        env['GIT_CONFIG_NOSYSTEM'] = "1"
        env['HOME'] = self.src_root
        self._assert_package_file_in_repo("git", env=env)
        
    @hg_dependent
    def test_4_hg_package_file_in_repo(self):
        """Test that if package.yaml not in hg repo, release is not allowed
        """
        env = dict(os.environ)
        # disable user/system hgrc loading...
        env['HGRCPATH'] = os.path.join(self.src_root, "hgrc")
        self._assert_package_file_in_repo("hg", env=env)

    @svn_dependent
    def test_5_svn_package_file_in_repo(self):
        """Test that if package.yaml not in svn repo, release is not allowed
        """
        self._assert_package_file_in_repo("svn")


if __name__ == '__main__':
    unittest.main()


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
