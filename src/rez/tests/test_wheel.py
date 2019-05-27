"""
test rez wheel
"""
import os
import stat
import shutil
import tempfile
import subprocess

from rez.tests.util import TempdirMixin, TestBase
from rez import wheel
from rez.resolved_context import ResolvedContext
from rez.package_maker__ import make_package
from rez.packages_ import iter_packages
from rez.util import which


def rmtree(path):
    # Rez write-protects the package.py files
    def del_rw(action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        os.remove(name)

    shutil.rmtree(path, onerror=del_rw)


class TestWheel(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = dict()
        cls.tempdir = tempfile.mkdtemp()

        python = which("python")
        assert python, "No Python found"

        result = subprocess.check_output(
            [python, "--version"],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
        )
        _, version = result.rstrip().split(" ", 1)
        version = version.split()[-1]
        version = int(version[0])

        with make_package("python", cls.tempdir) as maker:
            PATH = os.path.dirname(python)
            maker.version = str(version)
            maker.commands = "\n".join([
                "env.PATH.prepend('%s')" % PATH
            ])

        cls.context = ResolvedContext(
            ["python"],
            package_paths=[cls.tempdir]
        )

        cls.python_version = version

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()
        rmtree(cls.tempdir)

    def setUp(self):
        """Called for each test"""
        self.temprepo = tempfile.mkdtemp()

    def tearDown(self):
        rmtree(self.temprepo)

    def _execute(self, cmd):
        assert self.context.execute_shell(command=cmd).wait() == 0

    def _install(self, *packages, **kwargs):
        return wheel.install(packages, prefix=self.temprepo, **kwargs)

    def _installed_packages(self, name):
        return list(iter_packages(name, paths=[self.temprepo]))

    def _test_install(self, package, version):
        installed = self._install("%s==%s" % (package, version))
        assert installed, "Something should have been installed"

        names = [pkg.name for pkg in installed]
        versions = {
            package.name: str(package.version)
            for package in installed
        }

        self.assertIn(package, names)
        self.assertEqual(versions[package], version)

    def test_wheel_to_variants1(self):
        """Test wheel_to_variants with pure-Python wheel"""
        WHEEL = """\
Wheel-Version: 1.0
Generator: bdist_wheel 1.0
Root-Is-Purelib: true
Tag: py2-none-any
Tag: py3-none-any
"""

        variants = wheel.wheel_to_variants(WHEEL)
        self.assertEqual(variants, [])

    def test_wheel_to_variants2(self):
        """Test wheel_to_variants with compiled wheel"""
        WHEEL = """\
Wheel-Version: 1.0
Generator: bdist_wheel 1.0
Root-Is-Purelib: false
Tag: cp36-cp36m-win_amd64
"""

        variants = wheel.wheel_to_variants(WHEEL)
        self.assertEqual(variants, [
            "platform-%s" % wheel.platform_name(),
            "os-%s" % wheel.os_name(),
            "python-3.6",
        ])

    def test_wheel_to_variants3(self):
        """Test wheel_to_variants with unsupported WHEEL"""
        WHEEL = """\
Wheel-Version: 2.0
Generator: bdist_wheel 1.0
Root-Is-Purelib: false
Tag: cp36-cp36m-win_amd64
"""

        self.assertRaises(Exception, wheel.wheel_to_variants, WHEEL)

    def test_wheel_to_variants4(self):
        """Test wheel_to_variants with pure-Python, solo-version wheel"""
        WHEEL = """\
Wheel-Version: 1.0
Generator: bdist_wheel 1.0
Root-Is-Purelib: true
Tag: py2-none-any
"""

        variants = wheel.wheel_to_variants(WHEEL)
        self.assertEqual(variants, ["python-2"])

    def test_wheel_to_variants5(self):
        """Test wheel_to_variants with badly formatted WHEEL"""
        WHEEL = """\
I am b'a'd
"""

        self.assertRaises(Exception, wheel.wheel_to_variants, WHEEL)

    def test_purepython_23(self):
        """Install a pure-Python package compatible with both Python 2 and 3"""
        self._test_install("six", "1.12.0")

    def test_purepython_2(self):
        """Install a pure-Python package only compatible with Python 2"""
        self._test_install("futures", "3.2.0")

    def test_compiled(self):
        """Install a compiled Python package"""
        self._test_install("pyyaml", "5.1")

    def test_dependencies(self):
        """Install mkdocs, which carries lots of dependencies"""
        installed = self._install("mkdocs==1.0.4")
        assert installed, "Something should have been installed"

        names = [pkg.name for pkg in installed]
        package = {package.name: package for package in installed}["mkdocs"]
        versions = {
            package.name: str(package.version)
            for package in installed
        }

        self.assertEqual(versions["mkdocs"], "1.0.4")

        # From https://github.com/mkdocs/mkdocs/blob/1.0.4/setup.py#L58
        dependencies = (
            "click",
            "jinja2",
            "livereload",
            "markdown",
            "pyyaml",
            "tornado",
        )

        for name in dependencies:
            self.assertIn(name.lower(), names)

        # All requirements have been installed
        for req in package.requires:
            self.assertIn(req.name.lower(), names)

    def test_override_variant(self):
        """Test overriding variant"""
        installed = self._install("six", variants=["python-2"])
        assert installed, "Something should have been installed"
        package = installed[0].variants[0][0]
        self.assertEqual(str(package), "python-2")

    def test_existing_variant(self):
        """Test installing another variant"""

        # Package does not exist prior to install it
        self.assertEqual(self._installed_packages(name="six"), [])

        self._install("six", variants=["python-2"])
        package = self._installed_packages("six")[0]
        variants = [str(v[0]) for v in package.variants]
        self.assertEqual(variants, ["python-2"])

        # Make sure an install doesn't break or remove a prior variant
        # This normally happens when installing the same package
        # on another platform.
        self._install("six", variants=["python-3"])
        package = self._installed_packages("six")[0]
        variants = [str(v[0]) for v in package.variants]
        self.assertEqual(variants, ["python-2", "python-3"])

    def test_battery(self):
        """Install a variety of packages"""
        packages = [
            "Cython",
            "Jinja2",
            "MarkupSafe",
            "Pillow",
            "Qt.py",
            "blockdiag",
            "certifi",
            "excel",
            "funcparserlib",
            "lockfile",
            "lxml",
            "ordereddict",
            "pyblish-base",
            "pyblish-lite",
            "pyblish-maya",
            "setuptools",
            "urllib3",
            "webcolors",
            "xlrd",
            "six",
        ]

        if os.name == "nt":
            packages += [
                "pywin32",
                "pythonnet",
            ]

        self._install(*packages)

    def test_pyside2(self):
        """Install PySide2"""
        if self.python_version != 3:
            self.skipTest("PySide2 is not available on PyPI for Python 2")
