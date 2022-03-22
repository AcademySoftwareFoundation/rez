# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import print_function

from rez.packages import iter_packages
from rez.config import config
from rez.rex_bindings import VersionBinding
from rez.utils.execution import Popen
from rez.utils.backcompat import convert_old_command_expansions
from rez.utils.scope import scoped_formatter
from rez.vendor.six import six
from rez.system import system
import webbrowser
import sys


basestring = six.string_types[0]


class PackageHelp(object):
    """Object for extracting and viewing help for a package.

    Given a package and version range, help will be extracted from the latest
    package in the version range that provides it.
    """
    def __init__(self, package_name, version_range=None, paths=None, verbose=False):
        """Create a PackageHelp object.

        Args:
            package_name (str): Package to search.
            version_range (`VersionRange`): Versions to search.
        """
        self.package = None
        self._verbose = verbose
        self._sections = []

        # find latest package with a help entry
        package = None
        it = iter_packages(package_name, range_=version_range)
        packages = sorted(it, key=lambda x: x.version, reverse=True)
        for package_ in packages:
            if self._verbose:
                print("searching for help in %s..." % package_.uri)
            if package_.help:
                package = package_
                break

        if package:
            help_ = package.help
            if isinstance(help_, basestring):
                sections = [["Help", help_]]
            elif isinstance(help_, list):
                sections = help_
            if self._verbose:
                print("found %d help entries in %s." % (len(sections), package.uri))

            # create string formatter for help entries
            if package.num_variants == 0:
                base = package.base
                root = base
            else:
                variant = package.get_variant(0)
                base = variant.base
                root = variant.root

            formatter = scoped_formatter(
                base=base,
                root=root,
                config=config,
                version=VersionBinding(package.version),
                system=system)

            # format sections
            for section in sections:
                uri = section[1]
                uri = convert_old_command_expansions(uri)
                uri = uri.replace("$BROWSER", "").strip()
                uri = formatter.format(uri)
                section[1] = uri

            self.package = package
            self._sections = sections

    @property
    def success(self):
        """Return True if help was found, False otherwise."""
        return bool(self._sections)

    @property
    def sections(self):
        """Returns a list of (name, uri) 2-tuples."""
        return self._sections

    def open(self, section_index=0):
        """Launch a help section."""
        uri = self._sections[section_index][1]
        if len(uri.split()) == 1:
            self._open_url(uri)
        else:
            if self._verbose:
                print("running command: %s" % uri)

            with Popen(uri, shell=True) as p:
                p.wait()

    def print_info(self, buf=None):
        """Print help sections."""
        buf = buf or sys.stdout
        print("Sections:", file=buf)
        for i, section in enumerate(self._sections):
            print("  %s:\t%s (%s)" % (i + 1, section[0], section[1]), file=buf)

    @classmethod
    def open_rez_manual(cls):
        """Open the Rez user manual."""
        cls._open_url(config.documentation_url)

    @classmethod
    def _open_url(cls, url):
        if config.browser:
            cmd = [config.browser, url]
            if not config.quiet:
                print("running command: %s" % " ".join(cmd))
            p = Popen(cmd)
            p.communicate()
        else:
            if not config.quiet:
                print("opening URL in browser: %s" % url)
            webbrowser.open_new(url)
