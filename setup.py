from __future__ import with_statement
from distutils.command.install import install as _install
import fnmatch
import os
import os.path
import sys


try:
    from setuptools import setup, find_packages
    from setuptools.command.install import install
except ImportError:
    print >> sys.stderr, "install failed - requires setuptools"
    sys.exit(1)


if sys.version_info < (2, 6):
    print >> sys.stderr, "install failed - requires python v2.6 or greater"
    sys.exit(1)


os.environ['__rez_is_installing'] = '1'


def find_files(pattern, path=None, root="rez"):
    paths = []
    basepath = os.path.realpath(os.path.join("src", root))
    path_ = basepath
    if path:
        path_ = os.path.join(path_, path)

    for root, _, files in os.walk(path_):
        files = [x for x in files if fnmatch.fnmatch(x, pattern)]
        files = [os.path.join(root, x) for x in files]
        paths += [x[len(basepath):].lstrip(os.path.sep) for x in files]

    return paths


with open("src/rez/__init__.py") as f:
    code = f.read()
loc = code.split('\n')
ver_loc = [x for x in loc if x.startswith("__version__")][0]
version = ver_loc.split()[-1].replace('"','')

scripts = [
    "rezolve",
    "rez",
    "rez-config",
    "rez-build",
    "rez-release",
    "rez-env",
    "rez-context",
    "rez-suite",
    "rez-tools",
    "rez-interpret",
    "rez-test",
    "rez-bind",
    "rez-search",
    "rez-bootstrap",
    "rez-help",
    "bez",
    "_rez_fwd",  # TODO rename this _rez-forward for consistency
    "_rez-complete",
    "_rez_csh_complete"  # TODO is this needed?
]

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

        # add installed site to syspaths
        for path in ('', '.', './'):
            if path in sys.path:
                sys.path.remove(path)
        import site
        site.addsitedir(self.install_lib)
        sys.path.insert(0, self.install_lib)

        # run post-install hook
        from rez._sys._setup import post_install
        post_install(install_base_dir=self.install_lib,
                     install_scripts_dir=self.install_scripts,
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
    scripts=[os.path.join('bin', x) for x in scripts],
    include_package_data=True,
    package_dir = {'': 'src'},
    packages=find_packages('src', exclude=["tests"]),
    package_data = {
        'rez':
            ['rezconfig', 'logging.conf'] +
            ['README*'] +
            find_files('*.csh', '_sys') +
            find_files('*.sh', '_sys') +
            find_files('*.*', 'tests/data'),
        'rezplugins':
            find_files('rezconfig', root='rezplugins') +
            find_files('*.cmake', 'build_system', root='rezplugins')
        #'rezplugins': [
        #    'build_system/cmake_files/*.cmake',
        #]
    },
    classifiers = [
        "Development Status :: 3 - Alpha",
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
