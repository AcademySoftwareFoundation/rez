"""
test the pip utilities
"""
import unittest

import rez.vendor.packaging.version
import rez.vendor.distlib.database
from rez.vendor.version.version import VersionRange
from rez.vendor.version.requirement import Requirement
from rez.vendor.packaging.requirements import Requirement as packaging_Requirement
from rez.vendor.packaging.specifiers import SpecifierSet
from rez.exceptions import PackageRequestError
from rez.tests.util import TestBase

import rez.utils.pip


class TestPipUtils(TestBase):
    """
    """
    @classmethod
    def setUpClass(cls):
        cls.settings = {}
        cls.dist_path = cls.data_path("pip", "installed_distributions")

    def test_pip_to_rez_package_name(self):
        """
        """
        self.assertEqual(rez.utils.pip.pip_to_rez_package_name("asd"), "asd")
        self.assertEqual(rez.utils.pip.pip_to_rez_package_name("package-name"), "package_name")

    def test_pip_to_rez_version(self):
        """
        """
        self.assertEqual(rez.utils.pip.pip_to_rez_version("1.0.0"), "1.0.0")
        self.assertEqual(rez.utils.pip.pip_to_rez_version("0.9"), "0.9")
        self.assertEqual(rez.utils.pip.pip_to_rez_version("1.0a1"), "1.0.a1")
        self.assertEqual(rez.utils.pip.pip_to_rez_version("1.0.post1"), "1.0.post1")
        self.assertEqual(rez.utils.pip.pip_to_rez_version("1.0.dev1"), "1.0.dev1")
        self.assertEqual(rez.utils.pip.pip_to_rez_version("1.0+abc.7"), "1.0-abc.7")
        self.assertEqual(rez.utils.pip.pip_to_rez_version("1!2.3.4"), "2.3.4")
        self.assertEqual(rez.utils.pip.pip_to_rez_version("2.0b1pl0"), "2.0b1pl0")

    def test_pip_to_rez_version_raises(self):
        with self.assertRaises(rez.vendor.packaging.version.InvalidVersion):
            self.assertEqual(
                rez.utils.pip.pip_to_rez_version("2.0b1pl0", allow_legacy=False),
                "2.0b1pl0"
            )

    def test_pip_specifier_to_rez_requirement(self):
        """
        """
        def assertPipRezEquivalent(pip_spec_str, rez_req_str):
            pip_spec = SpecifierSet(pip_spec_str)
            self.assertEqual(
                rez.utils.pip.pip_specifier_to_rez_requirement(pip_spec),
                VersionRange(rez_req_str)
            )

        assertPipRezEquivalent(
            "==1",
            "1+<1.1"
        )
        assertPipRezEquivalent(
            ">1",
            "1.1+"
        )
        assertPipRezEquivalent(
            "<1",
            "<1"
        )
        assertPipRezEquivalent(
            ">=1",
            "1+"
        )
        assertPipRezEquivalent(
            "<=1",
            "<1.1"
        )
        assertPipRezEquivalent(
            "~=1.2",
            "1.2+<2"
        )
        assertPipRezEquivalent(
            "~=1.2.3",
            "1.2.3+<1.3"
        )
        assertPipRezEquivalent(
            "!=1",
            "<1|1.1+"
        )
        assertPipRezEquivalent(
            "!=1.2",
            "<1.2|1.2.1+"
        )
        assertPipRezEquivalent(
            "!=1.*",
            "<1|2+"
        )
        assertPipRezEquivalent(
            "!=1.2.*",
            "<1.2|1.3+"
        )
        assertPipRezEquivalent(
            ">=1.2.a1",
            "1.2.a1+"
        )
        assertPipRezEquivalent(
            "==1.*",
            "1"
        )
        assertPipRezEquivalent(
            ">=2.6, !=3.0.*, !=3.1.*, !=3.2.*, <4",
            "2.6+<3.0|3.3+<4"
        )

    def test_pip_specifier_to_rez_requirement_raises(self):
        """
        """
        with self.assertRaises(PackageRequestError):
            rez.utils.pip.pip_specifier_to_rez_requirement(SpecifierSet("<2,>3"))

    def test_packaging_req_to_rez_req(self):
        """
        """
        self.assertEqual(
            rez.utils.pip.packaging_req_to_rez_req(packaging_Requirement("package>1")),
            Requirement("package-1.1+")
        )
        self.assertEqual(
            rez.utils.pip.packaging_req_to_rez_req(packaging_Requirement("package")),
            Requirement("package")
        )
        self.assertEqual(
            rez.utils.pip.packaging_req_to_rez_req(packaging_Requirement("package[extra]")),
            Requirement("package")
        )

    def test_is_pure_python_package(self):
        """
        """
        dpath = rez.vendor.distlib.database.DistributionPath([self.dist_path])
        dist = list(dpath.get_distributions())[0]

        self.assertTrue(rez.utils.pip.is_pure_python_package(dist))

    def test_convert_distlib_to_setuptools_wrong(self):
        """
        """
        dpath = rez.vendor.distlib.database.DistributionPath([self.dist_path])
        dist = list(dpath.get_distributions())[0]
        dist.key = 'random-unexisting-package'

        self.assertEqual(rez.utils.pip.convert_distlib_to_setuptools(dist), None)

    def test_get_marker_sys_requirements(self):
        """
        """
        def assertSysRequirements(req_str, sys_reqs):
            self.assertEqual(
                rez.utils.pip.get_marker_sys_requirements(req_str),
                sys_reqs
            )

        assertSysRequirements(
            'implementation_name == "cpython"',
            ["python"]
        )
        assertSysRequirements(
            'implementation_version == "3.4.0"',
            ["python"]
        )
        assertSysRequirements(
            'platform_python_implementation == "Jython"',
            ["python"]
        )
        assertSysRequirements(
            'platform.python_implementation == "Jython"',
            ["python"]
        )
        assertSysRequirements(
            'python_implementation == "Jython"',
            ["python"]
        )
        assertSysRequirements(
            'sys_platform == "linux2"',
            ["platform"]
        )
        assertSysRequirements(
            'sys.platform == "linux2"',
            ["platform"]
        )
        assertSysRequirements(
            'os_name == "linux2"',
            ["platform"]
        )
        assertSysRequirements(
            'os.name == "linux2"',
            ["platform"]
        )
        assertSysRequirements(
            'platform_machine == "x86_64"',
            ["arch"]
        )
        assertSysRequirements(
            'platform.machine == "x86_64"',
            ["arch"]
        )
        assertSysRequirements(
            'platform_version == "#1 SMP Fri Apr 25 13:07:35 EDT 2014"',
            ["platform"]
        )
        assertSysRequirements(
            'platform.version == "#1 SMP Fri Apr 25 13:07:35 EDT 2014"',
            ["platform"]
        )
        assertSysRequirements(
            'platform_system == "Linux"',
            ["platform"]
        )
        assertSysRequirements(
            'platform_release == "5.2.8-arch1-1-ARCH"',
            ["platform"]
        )
        assertSysRequirements(
            'python_version == "3.7"',
            ["python"]
        )
        assertSysRequirements(
            'python_full_version == "3.7.4"',
            ["python"]
        )

    def test_normalize_requirement(self):
        """
        """
        def assertRequirements(requirement, expected, conditional_extras):
            """
            """
            result = rez.utils.pip.normalize_requirement(requirement)
            self.assertEqual([str(req) for req in result], [str(req) for req in expected])
            for index, req in enumerate(result):
                self.assertEqual(req.conditional_extras, conditional_extras[index])

        assertRequirements(
            "packageA",
            [packaging_Requirement("packageA")],
            [None]
        )
        assertRequirements(
            "mypkg ; extra == 'dev'",
            [packaging_Requirement("mypkg")],
            [set(["dev"])]
        )
        assertRequirements(
            'win-inet-pton ; (sys_platform == "win32" and python_version == "2.7") and extra == \'socks\'',
            [packaging_Requirement('win-inet-pton; (sys_platform == "win32" and python_version == "2.7")')],
            [set(["socks"])]
        )

        # PySocks (!=1.5.7,<2.0,>=1.5.6) ; extra == 'socks'
        assertRequirements(
            "PySocks (!=1.5.7,<2.0,>=1.5.6) ; extra == 'socks'",
            [packaging_Requirement("PySocks!=1.5.7,<2.0,>=1.5.6")],
            [set(["socks"])]
        )
        # certifi ; extra == 'secure'
        assertRequirements(
            "certifi ; extra == 'secure'",
            [packaging_Requirement("certifi")],
            [set(["secure"])]
        )
        # coverage (>=4.4)
        assertRequirements(
            'coverage (>=4.4)',
            [packaging_Requirement("coverage (>=4.4)")],
            [None]
        )
        # colorama ; sys_platform == "win32"
        assertRequirements(
            'colorama ; sys_platform == "win32"',
            [packaging_Requirement('colorama ; sys_platform == "win32"')],
            [None]
        )
        # pathlib2-2.3.4: {u'environment': u'python_version<"3.5"', u'requires': [u'scandir']}, {u'requires': [u'six']}
        assertRequirements(
            {
                u"environment": u'python_version<"3.5"',
                u"requires": [u"scandir"]
            },
            [packaging_Requirement('scandir; python_version < "3.5"')],
            [None]
        )

        # bleach-3.1.0: {u'requires': [u'six (>=1.9.0)', u'webencodings']}
        assertRequirements(
            {
                u"requires": [u"six (>=1.9.0)", u"webencodings"]
            },
            [packaging_Requirement("six (>=1.9.0)"), packaging_Requirement("webencodings")],
            [None, None]
        )

        assertRequirements(
            {
                u"requires": [u"six (>=1.9.0)", u'webencodings; sys_platform == "win32"']
            },
            [
                packaging_Requirement("six (>=1.9.0)"),
                packaging_Requirement('webencodings; sys_platform == "win32"')
            ],
            [None, None]
        )

        assertRequirements(
            {
                u"requires": [u"packageA"],
                u"extra": "doc"
            },
            [
                packaging_Requirement("packageA")
            ],
            [set(["doc"])]
        )

        assertRequirements(
            "mypkg ; extra == 'dev' or extra == 'doc'",
            [packaging_Requirement("mypkg")],
            [set(["dev", "doc"])]
        )

        assertRequirements(
            'mypkg ; extra == "dev" and sys_platform == "win32"',
            [packaging_Requirement('mypkg; sys_platform == "win32"')],
            [set(["dev"])]
        )

        assertRequirements(
            'mypkg ; sys_platform == "win32" and extra == "test"',
            [packaging_Requirement('mypkg; sys_platform == "win32"')],
            [set(["test"])]
        )


if __name__ == '__main__':
    unittest.main()
