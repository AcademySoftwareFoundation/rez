"""
Utility for displaying help for the given package. This is determined via the 
'help' entry in the package.yaml, if that entry does not exist then an error 
results.
"""

from rez.config import config
from rez.packages import iter_packages
from rez.util import convert_old_command_expansions
from rez.util import AttrDictWrapper, ObjectStringFormatter
from rez.vendor.version.requirement import Requirement
import webbrowser
import subprocess
import sys


def setup_parser(parser):

    parser.add_argument("pkg", metavar='PACKAGE', help="package name", nargs='?')
    parser.add_argument("section", type=int, metavar='SECTION', default=0, nargs='?')
    parser.add_argument("-m", "--manual", dest="manual", action="store_true",
                        default=False, help="Load the rez technical user manual")
    parser.add_argument("-e", "--entries", dest="entries", action="store_true",
                        default=False, help="Just print each help entry")


def command(opts, parser=None):

    if opts.manual or not opts.pkg:
        open_rez_manual()
        sys.exit(0)

    requirement = Requirement(opts.pkg)
    section = opts.section

    package = get_latest_package_with_help(requirement)
    if not package:
        print >> sys.stderr, "Could not find a package with help for %s." % requirement
        sys.exit(1)

    description = package.description

    print "Help found for:"
    print package.path

    if description:
        print 
        print "Description:"
        print description.strip()
        print 

    sections = get_help_sections_from_package(package)
    formatter = get_formatter_for_package(package)
    sections = format_sections(sections, formatter)

    if not sections:
        print >> sys.stderr, "Malformed or missing help info in %s." % package.path
        sys.exit(1)

    if section > len(sections):
        print >> sys.stderr, "Help for %s has no section %s." (package, section)
        section = 0

    if opts.entries:
        show_sections(sections)
        sys.exit(0)

    if section == 0:
        if len(sections) > 1:
            show_sections(sections)
            print >> sys.stderr, "A section number must be provided."
            sys.exit(1)

        else:
            section = 1

    open_section(sections[section - 1])


def open_url(url):

    if config.browser:
        cmd = "%s %s &" % (config.browser, url)
        subprocess.Popen(cmd, shell=True).communicate()
    else:
        webbrowser.open_new(url)


def open_rez_manual():

    open_url(config.documentation_url)


def open_section(section):

    uri = section[1]
    
    if len(uri.split()) == 1:
        open_url(uri)

    else:
        subprocess.Popen(uri, shell=True).communicate()


def get_latest_package_with_help(requirement):

    latest_package = None

    for package in iter_packages(requirement.name, range=requirement.range):
        is_latest = package.version > latest_package.version if latest_package else True

        if package.help is not None and is_latest:
            latest_package = package

    return latest_package


def expand_section_uri(uri, formatter):

    uri = convert_old_command_expansions(uri)
    uri = uri.replace("$BROWSER", "").strip()

    return formatter.format(uri)


def get_formatter_for_package(package):

    if package.num_variants == 0:
        base = os.path.dirname(package.path)
        root = base

    else:
        variant = package.get_variant(0)

        base = variant.base
        root = variant.root

    namespace = dict(base=base, root=root, config=config)
    formatter = ObjectStringFormatter(AttrDictWrapper(namespace), expand='unchanged')

    return formatter


def format_sections(sections, formatter):

    for section in sections:
        section[1] = expand_section_uri(section[1], formatter)

    return sections


def show_sections(sections):

    print "Sections:"

    for i, section in enumerate(sections):
        print "  %s:\t%s (%s)" % (i + 1, section[0], section[1])


def get_help_sections_from_package(package):

    sections = []
    help = package.help

    if isinstance(help, basestring):
        sections.add("Help", help)

    elif isinstance(help, list):
        sections = help

    return sections
