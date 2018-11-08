"""
test package serialisation
"""
import os
import StringIO
import rez.vendor.unittest2 as unittest

from rez.serialise import FileFormat
from rez.packages_ import get_developer_package
from rez.package_serialise import dump_package_data


class TestDumpYaml(unittest.TestCase):
    """Test yaml serialisation"""

    def setUp(self):
        """Setup run at each test"""
        super(TestDumpYaml, self).setUp()

        self.buf = StringIO.StringIO()

        path = os.path.realpath(os.path.dirname(__file__))
        self.packages_base_path = os.path.join(path, "data", "package_serialise")

    def test_simple(self):
        """Without include or exclude"""
        path = os.path.join(self.packages_base_path, "yaml")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.yaml
        )
        self.assertEqual(
            "name: rez\n\n"
            "version: 2.8.0.11\n\n"
            "description: Rez is a suite of tools for resolving a list of packages\n\n"
            "authors:\n"
            "- rez\n\n"
            "requires:\n"
            "- setuptools\n"
            "- python\n\n"
            "private_build_requires:\n"
            "- cmake-2.8\n\n"
            "variants:\n"
            "- - CentOS-6.2+<7\n"
            "  - python-2.6\n"
            "- - CentOS-6.2+<7\n"
            "  - python-2.7\n\n"
            "commands: |-\n"
            "  prependenv('PATH', '{root}/bin/rez/')\n"
            "  setenv('REZ_PATH', '{root}')\n\n"
            "help:\n"
            "- - Reference Guide\n"
            "  - $BROWSER http://nerdvegas.github.io/rez/\n\n"
            "uuid: 97937642-3646-4966-ab9c-8f337bbbce6a\n\n"
            "config_version: 0\n",
            self.buf.getvalue()
        )

    def test_include(self):
        """With include only"""
        path = os.path.join(self.packages_base_path, "yaml")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.yaml,
            include_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "name: rez\n\n"
            "variants:\n"
            "- - CentOS-6.2+<7\n"
            "  - python-2.6\n"
            "- - CentOS-6.2+<7\n"
            "  - python-2.7\n\n"
            "commands: |-\n"
            "  prependenv('PATH', '{root}/bin/rez/')\n"
            "  setenv('REZ_PATH', '{root}')\n",
            self.buf.getvalue()
        )

    def test_exclude(self):
        """With exclude only"""
        path = os.path.join(self.packages_base_path, "yaml")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.yaml,
            skip_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "version: 2.8.0.11\n\n"
            "description: Rez is a suite of tools for resolving a list of packages\n\n"
            "authors:\n"
            "- rez\n\n"
            "requires:\n"
            "- setuptools\n"
            "- python\n\n"
            "private_build_requires:\n"
            "- cmake-2.8\n\n"
            "help:\n"
            "- - Reference Guide\n"
            "  - $BROWSER http://nerdvegas.github.io/rez/\n\n"
            "uuid: 97937642-3646-4966-ab9c-8f337bbbce6a\n\n"
            "config_version: 0\n",
            self.buf.getvalue()
        )

    def test_include_exclude(self):
        """With exclude and exclude. Include wins over exclude"""
        path = os.path.join(self.packages_base_path, "yaml")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.yaml,
            include_attributes=["requires", "help", "variants"],
            skip_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "requires:\n"
            "- setuptools\n"
            "- python\n\n"
            "variants:\n"
            "- - CentOS-6.2+<7\n"
            "  - python-2.6\n"
            "- - CentOS-6.2+<7\n"
            "  - python-2.7\n\n"
            "help:\n"
            "- - Reference Guide\n"
            "  - $BROWSER http://nerdvegas.github.io/rez/\n",
            self.buf.getvalue()
        )


class TestDumpPy(unittest.TestCase):
    """Test Python serialisation"""

    def setUp(self):
        """Setup run at each test"""
        super(TestDumpPy, self).setUp()

        self.buf = StringIO.StringIO()

        path = os.path.realpath(os.path.dirname(__file__))
        self.packages_base_path = os.path.join(path, "data", "package_serialise")

    def test_simple(self):
        """Without include or exclude"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.py
        )
        self.assertEqual(
            "# -*- coding: utf-8 -*-\n\n"
            "name = 'usdBase'\n\n"
            "version = '0.8.al3.1.0'\n\n"
            "description = 'universal scene description'\n\n"
            "requires = [\n"
            "    'stdlib-4.8',\n"
            "    'tbb-4.4',\n"
            "    'ilmbase-2.2'\n"
            "]\n\n"
            "private_build_requires = [\n"
            "    'cmake-2.8',\n"
            "    'gcc-4.8',\n"
            "    'gdb'\n"
            "]\n\n"
            "variants = [\n"
            "    ['AL_boost-1.55.0', 'AL_boost_python-1.55'],\n"
            "    ['boost-1.55.0', 'boost_python-1.55']\n"
            "]\n\n"
            "def commands():\n"
            "    prependenv('PATH', '{root}/bin')\n"
            "    prependenv('PYTHONPATH', '{root}/lib/python')\n"
            "    prependenv('LD_LIBRARY_PATH', '{root}/lib')\n\n"
            "use_chroot = True\n",
            self.buf.getvalue()
        )

    def test_include(self):
        """With include only"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.py,
            include_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "# -*- coding: utf-8 -*-\n\n"
            "name = 'usdBase'\n\n"
            "variants = [\n"
            "    ['AL_boost-1.55.0', 'AL_boost_python-1.55'],\n"
            "    ['boost-1.55.0', 'boost_python-1.55']\n"
            "]\n\n"
            "def commands():\n"
            "    prependenv('PATH', '{root}/bin')\n"
            "    prependenv('PYTHONPATH', '{root}/lib/python')\n"
            "    prependenv('LD_LIBRARY_PATH', '{root}/lib')\n",
            self.buf.getvalue()
        )

    def test_exclude(self):
        """With exclude only"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.py,
            skip_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "# -*- coding: utf-8 -*-\n\n"
            "version = '0.8.al3.1.0'\n\n"
            "description = 'universal scene description'\n\n"
            "requires = [\n"
            "    'stdlib-4.8',\n"
            "    'tbb-4.4',\n"
            "    'ilmbase-2.2'\n"
            "]\n\n"
            "private_build_requires = [\n"
            "    'cmake-2.8',\n"
            "    'gcc-4.8',\n"
            "    'gdb'\n"
            "]\n\n"
            "use_chroot = True\n",
            self.buf.getvalue()
        )

    def test_include_exclude(self):
        """With exclude and exclude. Include wins over exclude"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.py,
            include_attributes=["requires", "help", "variants"],
            skip_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "# -*- coding: utf-8 -*-\n\n"
            "requires = [\n"
            "    'stdlib-4.8',\n"
            "    'tbb-4.4',\n"
            "    'ilmbase-2.2'\n"
            "]\n\n"
            "variants = [\n"
            "    ['AL_boost-1.55.0', 'AL_boost_python-1.55'],\n"
            "    ['boost-1.55.0', 'boost_python-1.55']\n"
            "]\n",
            self.buf.getvalue()
        )


class TestDumpTxt(unittest.TestCase):
    """Test text serialisation"""

    def setUp(self):
        """Setup run at each test"""
        super(TestDumpTxt, self).setUp()

        self.buf = StringIO.StringIO()

        path = os.path.realpath(os.path.dirname(__file__))
        self.packages_base_path = os.path.join(path, "data", "package_serialise")

    def test_simple(self):
        """Without include or exclude. Separator: '' and pretty = False"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.txt
        )
        self.assertEqual(
            "usdBase\n"
            "0.8.al3.1.0\n"
            "universal scene description\n"
            "['stdlib-4.8', 'tbb-4.4', 'ilmbase-2.2']\n"
            "['cmake-2.8', 'gcc-4.8', 'gdb']\n"
            "[['AL_boost-1.55.0', 'AL_boost_python-1.55'], ['boost-1.55.0', 'boost_python-1.55']]\n"
            "prependenv('PATH', '{root}/bin')\n"
            "prependenv('PYTHONPATH', '{root}/lib/python')\n"
            "prependenv('LD_LIBRARY_PATH', '{root}/lib')\n"
            "True\n",
            self.buf.getvalue()
        )

    def test_include(self):
        """With include only"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.txt,
            include_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "usdBase\n"
            "[['AL_boost-1.55.0', 'AL_boost_python-1.55'], ['boost-1.55.0', 'boost_python-1.55']]\n"
            "prependenv('PATH', '{root}/bin')\n"
            "prependenv('PYTHONPATH', '{root}/lib/python')\n"
            "prependenv('LD_LIBRARY_PATH', '{root}/lib')\n",
            self.buf.getvalue()
        )

    def test_exclude(self):
        """With exclude only"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.txt,
            skip_attributes=["name", "variants", "commands"]
        )
        self.assertEqual(
            "0.8.al3.1.0\n"
            "universal scene description\n"
            "['stdlib-4.8', 'tbb-4.4', 'ilmbase-2.2']\n"
            "['cmake-2.8', 'gcc-4.8', 'gdb']\n"
            "True\n",
            self.buf.getvalue()
        )

    def test_include_exclude(self):
        """With exclude and exclude. Include wins over exclude"""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.txt,
            include_attributes=["requires", "help", "variants"],
            skip_attributes=["name", "variants", "commands"],
        )
        self.assertEqual(
            "['stdlib-4.8', 'tbb-4.4', 'ilmbase-2.2']\n"
            "[['AL_boost-1.55.0', 'AL_boost_python-1.55'], ['boost-1.55.0', 'boost_python-1.55']]\n",
            self.buf.getvalue()
        )

    def test_coma_separator_raw(self):
        """Test with a coma as a separator in raw mode. It won't have an effect."""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.txt,
            separator=" , ",
            include_attributes=["requires"]
        )

        self.assertEqual("['stdlib-4.8', 'tbb-4.4', 'ilmbase-2.2']\n", self.buf.getvalue())

    def test_coma_without_separator_pretty(self):
        """Test without a separator in pretty mode."""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.txt,
            include_attributes=["variants"],
            pretty=True
        )
        self.assertEqual(
            "AL_boost-1.55.0 AL_boost_python-1.55\n"
            "boost-1.55.0 boost_python-1.55\n",
            self.buf.getvalue()
        )

    def test_coma_separator_pretty(self):
        """Test with a coma as a separator in pretty mode."""
        path = os.path.join(self.packages_base_path, "py")
        package = get_developer_package(path)

        dump_package_data(
            package.validated_data().copy(),
            self.buf,
            format_=FileFormat.txt,
            separator=" , ",
            include_attributes=["variants"],
            pretty=True
        )

        self.assertEqual(
            "AL_boost-1.55.0 , AL_boost_python-1.55\n"
            "boost-1.55.0 , boost_python-1.55\n",
            self.buf.getvalue()
        )
