"""
test rez pip
"""

from rez.tests.util import TempdirMixin, TestBase
from rez import pip


class TestPip(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = dict()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_classifiers_none(self):
        """Test no relevant classifiers"""
        classifiers = [
            "Development Status :: 4 - Beta",
            "License :: OSI Approved :: MIT License",
            "Intended Audience :: Developers",
            "Programming Language :: Ruby",
            "Topic :: Software Development",
            "Topic :: System :: Software Distribution"
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, [])

    def test_classifiers_all(self):
        """Test matches to all available classifiers

        Commit:
            https://github.com/mkdocs/mkdocs/blob/
            ddf84aefd5f43bca53228c49d503707457175018/setup.py

        """

        classifiers = [
            "Operating System :: Microsoft :: Windows 10",
            "Programming Language :: Python :: 2.6",
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, [
            "platform-windows", "python-2"])

    def test_classifiers_os_independent(self):
        """Test OS independent pip classifiers"""
        classifiers = [
            "Operating System :: OS Independent",
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, [])

    def test_classifiers_os_windows(self):
        """Test Windows classifier"""
        classifiers = [
            "Operating System :: Microsoft",
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, ["platform-windows"])

    def test_classifiers_os_linux(self):
        """Test Linux classifiers"""
        classifiers = [
            "Operating System :: POSIX",
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, ["platform-linux"])

    def test_classifiers_python_2(self):
        """Test Python dual-compatible"""
        classifiers = [
            "Programming Language :: Python",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 2.6",
            "Programming Language :: Python :: 2.7",
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, ["python-2"])

    def test_classifiers_python_2_only(self):
        """Test Python 2-only"""
        classifiers = [
            "Programming Language :: Python :: 2 :: Only",
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, ["python-2"])

    def test_classifiers_python_3_only(self):
        """Test Python 3-only"""
        classifiers = [
            "Programming Language :: Python :: 3 :: Only",
        ]

        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, ["python-3"])

    def test_classifiers_mkdocs(self):
        """Test real-world classifiers from mkdocs

        Commit:
            https://github.com/mkdocs/mkdocs/blob/
            ddf84aefd5f43bca53228c49d503707457175018/setup.py

        """

        classifiers = [
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            "Programming Language :: Python :: Implementation :: CPython",
            "Programming Language :: Python :: Implementation :: PyPy",
            'Topic :: Documentation',
            'Topic :: Text Processing',
        ]

        # Compatible with both Python's, no need for variant
        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, [])

    def test_classifiers_six(self):
        """Test real-world classifiers from six

        Commit:
            https://github.com/benjaminp/six/blob/
            8da94b8a153ceb0d6417d76729ba75e80eaa75c1/setup.py#L22

        """

        classifiers = [
            "Development Status :: 5 - Production/Stable",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 3",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Topic :: Software Development :: Libraries",
            "Topic :: Utilities",
        ]

        # Compatible with both Python's, no need for variant
        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, [])

    def test_classifiers_jinja2(self):
        """Test real-world classifiers from jinja2

        Commit:
            https://github.com/benjaminp/six/blob/
            8da94b8a153ceb0d6417d76729ba75e80eaa75c1/setup.py#L22

        """

        classifiers = [
            'Development Status :: 5 - Production/Stable',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: Implementation :: CPython',
            'Programming Language :: Python :: Implementation :: PyPy',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: Text Processing :: Markup :: HTML'
        ]

        # Compatible with both Python's, no need for variant
        variants = pip.classifiers_to_variants(classifiers)
        self.assertListEqual(variants, [])
