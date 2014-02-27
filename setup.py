from __future__ import with_statement
from setuptools import setup, find_packages
from setuptools.command.install import install
from distutils.command.install import install as _install
import os
import os.path
import sys


if sys.version_info < (2,6):
    print >> sys.stderr, "Rez requires python v2.6 or greater"
    sys.exit(0)

with open("rez/__init__.py") as f:
    code = f.read()
loc = code.split('\n')
ver_loc = [x for x in loc if x.startswith("__version__")][0]
#version = ver_loc.split()[-1].replace('"','')
version = "2.0.PRE-ALPHA.24"

scripts = [
    "rezolve",
    "rez",
    "rez-settings",
    "rez-env",
    "rez-context",
    "rez-exec",
    "_rez_csh_complete"
]

requires = [
    # pysvn is problematic, it doesn't play nice with setuptools. If you need
    # it, install it separately.
    # "pysvn >= 1.7.2"
    "PyYAML >= 3.9",
    "Yapsy >= 1.10.0",
    "python-memcached >= 1.0",
    "GitPython >= 0.3.2.RC1"
]

if sys.version_info < (2,7):
    requires.append('argparse')

# post install hook. Don't believe google - this is how you do it.
class install_(install):
    def run(self):
        ret = None
        if self.old_and_unmanageable or self.single_version_externally_managed:
            ret = _install.run(self)
        else:
            caller = sys._getframe(2)
            caller_module = caller.f_globals.get('__name__','')
            caller_name = caller.f_code.co_name

            if caller_module != 'distutils.dist' or caller_name!='run_commands':
                _install.run(self)
            else:
                self.do_egg_install()

        import site
        os.environ['__rez_is_installing'] = '1'
        site.addsitedir(self.install_lib)
        sys.path.insert(0, self.install_lib)
        from rez._sys import _setup
        _setup.post_install(install_base_dir=self.install_lib,
                            install_scripts_dir=self.install_scripts,
                            version=version,
                            scripts=scripts)
        return ret

setup(
    name="rez",
    version=version,
    description=("A cross-platform packaging system that can build and "
                "install multiple version of packages, and dynamically "
                "configure resolved environments at runtime."),
    keywords="package resolve version build install software management",
    long_description=None,
    url="https://github.com/nerdvegas/rez",
    author="Allan Johns",
    author_email="nerdvegas@gmail.com",
    license="LGPL",
    cmdclass={'install': install_},
    scripts=[os.path.join('bin2',x) for x in scripts],
    packages=find_packages(exclude=['tests']),
    install_requires=requires,
    include_package_data=True,
    package_data = {
        'rez': [
            'rezconfig',
            'README*',
            '*.yapsy-plugin',
            'cmake/*.cmake',
            '_sys/*'
        ]
    },
    classifiers = [
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: Software Development",
        "Topic :: System :: Software Distribution"
    ]
)
