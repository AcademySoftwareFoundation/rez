"""
Python packaging related utilities.
"""
import os.path
from email.parser import Parser

import pkg_resources

from rez.vendor.packaging.version import (
    parse as packaging_parse,
    LegacyVersion as packaging_LegacyVersion,
    InvalidVersion as packaging_InvalidVersion
)
from rez.vendor.packaging.requirements import Requirement as packaging_Requirement
from rez.vendor.version.requirement import Requirement
from rez.vendor.version.version import Version, VersionRange

from rez.utils.logging_ import print_warning
from rez.exceptions import PackageRequestError
from rez.system import System


def pip_to_rez_package_name(dist_name):
    """Convert a distribution name to a rez compatible name.

    The rez package name can't be simply set to the dist name, because some
    pip packages have hyphen in the name. In rez this is not a valid package
    name (it would be interpreted as the start of the version).

    Example: my-pkg-1.2 is 'my', version 'pkg-1.2'.

    Args:
        dist_name (str): Distribution name to convert.

    Returns:
        str: Rez-compatible package name.
    """
    return dist_name.replace("-", "_")


def pip_to_rez_version(dist_version, allow_legacy=True):
    """Convert a distribution version to a rez compatible version.

    TODO [AJ] needs a table of example conversions.

    The python version schema specification isn't 100% compatible with rez.

    1: version epochs (they make no sense to rez, so they'd just get stripped
       of the leading N!;
    2: python versions are case insensitive, so they should probably be
       lowercased when converted to a rez version.
    3: local versions are also not compatible with rez

    The canonical public version identifiers MUST comply with the following scheme:
    [N!]N(.N)*[{a|b|rc}N][.postN][.devN]

    Epoch segment: N! - skip
    Release segment: N(.N)* 0 as is
    Pre-release segment: {a|b|c|rc|alpha|beta|pre|preview}N - always lowercase
    Post-release segment: .{post|rev|r}N - always lowercase
    Development release segment: .devN - always lowercase

    Local version identifiers MUST comply with the following scheme:
    <public version identifier>[+<local version label>] - use - instead of +

    Args:
        dist_version (str): The distribution version to be converted.
        allow_legacy (bool): Flag to allow/disallow PEP440 incompatibility.

    Returns:
        str: Rez-compatible equivalent version string.

    Raises:
        InvalidVersion: When legacy mode is not allowed and a PEP440
        incompatible version is detected.

    .. _PEP 440 (all possible matches):
        https://www.python.org/dev/peps/pep-0440/#appendix-b-parsing-version-strings-with-regular-expressions

    .. _Core utilities for Python packages:
        https://packaging.pypa.io/en/latest/version/

    """
    pkg_version = packaging_parse(dist_version)

    if isinstance(pkg_version, packaging_LegacyVersion):
        if allow_legacy:
            print_warning(
                "Invalid PEP440 version detected: %r. "
                "Reverting to legacy mode." % pkg_version
            )
            # this will always be the entire version string
            return pkg_version.base_version.lower()
        else:
            raise packaging_InvalidVersion(
                "Version: {} is not compatible with PEP440.".format(dist_version)
            )

    # the components of the release segment excluding epoch or any
    # prerelease/development/postrelease suffixes
    rez_version = '.'.join(str(i) for i in pkg_version.release)

    if pkg_version.is_prerelease and pkg_version.pre:
        # Additional check is necessary because dev releases are also considered
        # prereleases pair of the prerelease phase (the string "a", "b", or "rc")
        # and the prerelease number the following conversions take place:
        # * a --> a
        # * alpha --> a
        # * b --> b
        # * beta --> b
        # * c --> c
        # * rc --> rc
        # * pre --> rc
        # * preview --> rc
        #
        phase, number = pkg_version.pre
        rez_version += '.' + phase + str(number)

    if pkg_version.is_postrelease:
        # this attribute will be the postrelease number (an integer)
        # the following conversions take place:
        # * post --> post
        # * rev --> post
        # * r --> post
        #
        rez_version += ".post" + str(pkg_version.post)

    if pkg_version.is_devrelease:
        # this attribute will be the development release number (an integer)
        rez_version += ".dev" + str(pkg_version.dev)

    if pkg_version.local:
        # representation of the local version portion is any
        # the following conversions take place:
        # 1.0[+ubuntu-1] --> 1.0[-ubuntu.1]
        rez_version += "-" + pkg_version.local

    return rez_version


def pip_specifier_to_rez_requirement(specifier):
    """Convert PEP440 version specifier to rez equivalent.

    See https://www.python.org/dev/peps/pep-0440/#version-specifiers

    Note that version numbers in the specifier are converted to rez equivalents
    at the same time. Thus a specifier like '<1.ALPHA2' becomes '<1.a2'.

    Note that the conversion is not necessarily exact - there are cases in
    PEP440 that have no equivalent in rez versioning. Most of these are
    specifiers that involve pre/post releases, which don't exist in rez (or
    rather, they do exist in the sense that '1.0.post1' is a valid rez version
    number, but it has no special meaning).

    Note also that the specifier is being converted into rez format, but in a
    way that still expresses how _pip_ interprets the specifier. For example,
    '==1' is a valid version range in rez, but '==1' has a different meaning to
    pip than it does to rez ('1.0' matches '==1' in pip, but not in rez). This
    is why '==1' is converted to '1+<1.1' in rez, rather than '==1'.

    Example conversions:

        |   PEP440    |     rez     |
        |-------------|-------------|
        | ==1         | 1+<1.1      |
        | ==1.*       | 1           |
        | >1          | 1.1+        |
        | <1          | <1          |
        | >=1         | 1+          |
        | <=1         | <1.1        |
        | ~=1.2       | 1.2+<2      |
        | ~=1.2.3     | 1.2.3+<1.3  |
        | !=1         | <1|1.1+     |
        | !=1.2       | <1.2|1.2.1+ |
        | !=1.*       | <1|2+       |
        | !=1.2.*     | <1.2|1.3+   |

    Args:
        specifier (`package.SpecifierSet`): Pip specifier.

    Returns:
        `VersionRange`: Equivalent rez version range.
    """
    def is_release(rez_ver):
        parts = rez_ver.split('.')
        try:
            _ = int(parts[-1])  # noqa
            return True
        except:
            return False

    # 1 --> 2; 1.2 --> 1.3; 1.a2 -> 1.0
    def next_ver(rez_ver):
        parts = rez_ver.split('.')
        if is_release(rez_ver):
            parts = parts[:-1] + [str(int(parts[-1]) + 1)]
        else:
            parts = parts[:-1] + ["0"]
        return '.'.join(parts)

    # 1 --> 1.1; 1.2 --> 1.2.1; 1.a2 --> 1.0
    def adjacent_ver(rez_ver):
        if is_release(rez_ver):
            return rez_ver + ".1"
        else:
            parts = rez_ver.split('.')
            parts = parts[:-1] + ["0"]
            return '.'.join(parts)

    def convert_spec(spec):
        def parsed_rez_ver():
            v = spec.version.replace(".*", "")
            return pip_to_rez_version(v)

        def fmt(txt):
            v = parsed_rez_ver()
            vnext = next_ver(v)
            vadj = adjacent_ver(v)
            return txt.format(V=v, VNEXT=vnext, VADJ=vadj)

        # ==1.* --> 1
        if spec.operator == "==" and spec.version.endswith(".*"):
            return fmt("{V}")

        # ==1 --> 1+<1.1
        if spec.operator == "==":
            return fmt("{V}+<{VADJ}")

        # >=1 --> 1+
        if spec.operator == ">=":
            return fmt("{V}+")

        # >1 --> 1.1+
        if spec.operator == ">":
            return fmt("{VADJ}+")

        # <= 1 --> <1.1
        if spec.operator == "<=":
            return fmt("<{VADJ}")

        # <1 --> <1
        if spec.operator == "<":
            return fmt("<{V}")

        # ~=1.2 --> 1.2+<2; ~=1.2.3 --> 1.2.3+<1.3
        if spec.operator == "~=":
            v = Version(parsed_rez_ver())
            v = v.trim(len(v) - 1)
            v_next = next_ver(str(v))
            return fmt("{V}+<" + v_next)

        # !=1.* --> <1|2+; !=1.2.* --> <1.2|1.3+
        if spec.operator == "!=" and spec.version.endswith(".*"):
            return fmt("<{V}|{VNEXT}+")

        # !=1 --> <1|1.1+; !=1.2 --> <1.2|1.2.1+
        if spec.operator == "!=":
            return fmt("<{V}|{VADJ}+")

        raise PackageRequestError(
            "Don't know how to convert PEP440 specifier %r "
            "into rez equivalent" % specifier
        )

    # convert each spec into rez equivalent
    ranges = list(map(convert_spec, specifier))

    # AND together ranges
    total_range = VersionRange(ranges[0])

    for range_ in ranges[1:]:
        range_ = VersionRange(range_)
        total_range = total_range.intersection(range_)

        if total_range is None:
            raise PackageRequestError(
                "PEP440 specifier %r converts to a non-intersecting rez "
                "version range" % specifier
            )

    return total_range


def packaging_req_to_rez_req(packaging_req):
    """Convert packaging requirement object to equivalent rez requirement.

    Note that environment markers are ignored.

    Args:
        packaging_req (`packaging.requirements.Requirement`): Packaging requirement.

    Returns:
        `Requirement`: Equivalent rez requirement object.
    """
    if packaging_req.extras:
        print_warning(
            "Ignoring extras requested on %r - "
            "this is not yet supported" % str(packaging_req)
        )

    rez_req_str = pip_to_rez_package_name(packaging_req.name)

    if packaging_req.specifier:
        range_ = pip_specifier_to_rez_requirement(packaging_req.specifier)
        rez_req_str += '-' + str(range_)

    return Requirement(rez_req_str)


def is_pure_python_package(installed_dist):
    """Determine if a dist is pure python.

    Args:
        installed_dist (`distlib.database.InstalledDistribution`): Distribution
            to test.

    Returns:
        bool: True if dist is pure python
    """
    setuptools_dist = convert_distlib_to_setuptools(installed_dist)

    # see https://www.python.org/dev/peps/pep-0566/#json-compatible-metadata
    wheel_data = setuptools_dist.get_metadata('WHEEL')
    wheel_data = Parser().parsestr(wheel_data)

    # see https://www.python.org/dev/peps/pep-0427/#what-s-the-deal-with-purelib-vs-platlib
    return (wheel_data.get("Root-Is-Purelib", "").lower() == "true")


def get_rez_requirements(installed_dist, python_version, name_casings=None):
    """Get requirements of the given dist, in rez-compatible format.

    Example result:

        {
            "requires": ["foo-1.2+<2"],
            "variant_requires": ["future", "python-2.7"],
            "metadata": {
                # metadata pertinent to rez
                ...
            }
        }

    Each requirement has had its package name converted to the rez equivalent.
    The 'variant_requires' key contains requirements specific to the current
    variant.

    TODO: Currently there is no way to reflect extras that may have been chosen
    for this pip package. We need to wait for rez "package features" before this
    will be possible. You probably shouldn't use extras presently.

    Args:
        installed_dist (`distlib.database.InstalledDistribution`): Distribution
            to convert.
        python_version (`Version`): Python version used to perform the
            installation.
        name_casings (list of str): A list of pip package names in their correct
            casings (eg, 'Foo' rather than 'foo'). Any requirement whose name
            case-insensitive-matches a name in this list, is set to that name.
            This is needed because pip package names are case insensitive, but
            rez is case-sensitive. So a package may list a requirement for package
            'foo', when in fact the package that pip has downloaded is called 'Foo'.
            Be sure to provide names in PIP format, not REZ format (the pip package
            'foo-bah' will be converted to 'foo_bah' in rez).

    Returns:
        Dict: See example above.
    """
    _system = System()
    result_requires = []
    result_variant_requires = []

    # create cased names lookup
    name_mapping = dict((x.lower(), x) for x in (name_casings or []))

    # requirements such as platform, arch, os, and python
    sys_requires = set(["python"])

    # assume package is platform- and arch- specific if it isn't pure python
    is_pure_python = is_pure_python_package(installed_dist)
    if not is_pure_python:
        sys_requires.update(["platform", "arch"])

    # evaluate wrt python version, which may not be the current interpreter version
    marker_env = {
        "python_full_version": str(python_version),
        "python_version": str(python_version.trim(2)),
        "implementation_version": str(python_version)
    }

    # Note: This is supposed to give a requirements list that has already been
    # filtered down based on the extras requested at install time, and on any
    # environment markers present. However, this is not working in distlib. The
    # package gets assigned a LegacyMetadata metadata object (only if a package metadata
    # version is not equal to 2.0) and in that code path, this filtering
    # doesn't happen.
    #
    # See: vendor/distlib/metadata.py#line-892
    #
    requires = installed_dist.run_requires

    # filter requirements
    for req_ in requires:
        reqs = normalize_requirement(req_)

        for req in reqs:
            # skip if env marker is present and doesn't evaluate
            if req.marker and not req.marker.evaluate(environment=marker_env):
                continue

            # skip if req is conditional on extras that weren't requested
            if req.conditional_extras and not \
                    (set(installed_dist.extras or []) & set(req.conditional_extras)):
                continue

            if req.conditional_extras:
                print_warning(
                    "Skipping requirement %r - conditional requirements are "
                    "not yet supported", str(req)
                )
                continue

            # Inspect marker(s) to see if this requirement should be varianted.
            # Markers may also cause other system requirements to be added to
            # the variant.
            #
            to_variant = False

            if req.marker:
                marker_reqs = get_marker_sys_requirements(str(req.marker))

                if marker_reqs:
                    sys_requires.update(marker_reqs)
                    to_variant = True

            # remap the requirement name
            remapped = name_mapping.get(req.name.lower())
            if remapped:
                req.name = remapped

            # convert the requirement to rez equivalent
            rez_req = str(packaging_req_to_rez_req(req))

            if to_variant:
                result_variant_requires.append(rez_req)
            else:
                result_requires.append(rez_req)

    # prefix variant with system requirements
    sys_variant_requires = []

    if "platform" in sys_requires:
        sys_variant_requires.append("platform-%s" % _system.platform)

    if "arch" in sys_requires:
        sys_variant_requires.append("arch-%s" % _system.arch)

    if "os" in sys_requires:
        sys_variant_requires.append("os-%s" % _system.os)

    if "python" in sys_requires:
        # Add python variant requirement. Note that this is always MAJOR.MINOR,
        # because to do otherwise would mean analysing any present env markers.
        # This could become quite complicated, and could also result in strange
        # python version ranges in the variants.
        #
        sys_variant_requires.append("python-%s" % str(python_version.trim(2)))

    return {
        "requires": result_requires,
        "variant_requires": sys_variant_requires + result_variant_requires,
        "metadata": {
            "is_pure_python": is_pure_python
        }
    }


def convert_distlib_to_setuptools(installed_dist):
    """Get the setuptools equivalent of a distlib installed dist.

    Args:
        installed_dist (`distlib.database.InstalledDistribution`: Distribution
            to convert.

    Returns:
        `pkg_resources.DistInfoDistribution`: Equivalent setuptools dist object.
    """
    path = os.path.dirname(installed_dist.path)
    setuptools_dists = pkg_resources.find_distributions(path)

    for setuptools_dist in setuptools_dists:
        if setuptools_dist.key == installed_dist.key:
            return setuptools_dist

    return None


def get_marker_sys_requirements(marker):
    """Get the system requirements that an environment marker introduces.

    Consider:

        'foo (>1.2) ; python_version == "3" and platform_machine == "x86_64"'

    This example would cause a requirement on python, platform, and arch
    (platform as a consequence of requirement on arch).

    See:
    * vendor/packaging/markers.py:line=76
    * https://www.python.org/dev/peps/pep-0508/#id23

    Args:
        marker (str): Environment marker string, eg 'python_version == "3"'.

    Returns:
        List of str: System requirements (unversioned).
    """
    _py = "python"
    _plat = "platform"
    _arch = "arch"

    sys_requires_lookup = {
        # TODO There is no way to associate a python version with its implementation
        # currently (ie CPython etc). When we have "package features", we may be
        # able to manage this; ignore for now
        "implementation_name": [_py],  # PEP-0508
        "implementation_version": [_py],  # PEP-0508
        "platform_python_implementation": [_py],  # PEP-0508
        "platform.python_implementation": [_py],  # PEP-0345
        "python_implementation": [_py],  # setuptools legacy. Same as platform_python_implementation

        "sys.platform": [_plat],  # PEP-0345
        "sys_platform": [_plat],  # PEP-0508

        # note that this maps to python's os.name, which does not mean distro
        # (as 'os' does in rez). See https://docs.python.org/2/library/os.html#os.name
        "os.name": [_plat],  # PEP-0345
        "os_name": [_plat],  # PEP-0508

        "platform.machine": [_arch],  # PEP-0345
        "platform_machine": [_arch],  # PEP-0508

        # TODO hmm, we never variant on plat version, let's leave this for now...
        "platform.version": [_plat],  # PEP-0345
        "platform_version": [_plat],  # PEP-0508

        # somewhat ambiguous cases
        "platform_system": [_plat],  # PEP-0508
        "platform_release": [_plat],  # PEP-0508
        "python_version": [_py],  # PEP-0508
        "python_full_version": [_py]  # PEP-0508
    }

    sys_requires = set()

    # note: packaging lib already delimits with whitespace
    marker_parts = marker.split()

    for varname, sys_reqs in sys_requires_lookup.items():
        if varname in marker_parts:
            sys_requires.update(sys_reqs)

    return list(sys_requires)


def normalize_requirement(requirement):
    """Normalize a package requirement.

    Requirements from distlib packages can be a mix of string- or dict- based
    formats, as shown here:

    * https://www.python.org/dev/peps/pep-0508/#environment-markers
    * https://legacy.python.org/dev/peps/pep-0426/#environment-markers

    There's another confusing case that this code deals with. Consider these two
    requirements:

        # means: reportlab is a requirement of this package when the 'pdf' extra is requested
        Requires-Dist: reportlab; extra == 'pdf'

        means: this package requires libexample, with its 'test' extras
        Requires-Dist: libexample[test]

    See https://packaging.python.org/specifications/core-metadata/#provides-extra-multiple-use

    The packaging lib doesn't do a good job of expressing this - the first form
    of extras use just gets embedded in the environment marker. This function
    parses the extra from the marker, and stores it onto the resulting
    `packaging.Requirement` object in a 'conditional_extras' attribute. It also
    removes the extra from the marker (otherwise the marker cannot evaluate).
    Even though you can specify `environment` in `packaging.Marker.evaluate`,
    you can only supply a single 'extra' key in the env, so this can't be used
    to correctly evaluate if multiple extras were requested.

    Args:
        requirement (str or dict): Requirement, for eg from
            `distlib.database.InstalledDistribution.run_requires`.

    Returns:
        List of `packaging.requirements.Requirement`: Normalized requirements.
        Note that a list is returned, because the PEP426 format can define
        multiple requirements.
    """
    def reconstruct(req, marker_str=None, conditional_extras=None):
        new_req_str = req.name

        if req.specifier:
            new_req_str += " (%s)" % str(req.specifier)

        if marker_str is None and req.marker:
            marker_str = str(req.marker)

        if marker_str:
            new_req_str += " ; " + marker_str

        new_req = packaging_Requirement(new_req_str)
        setattr(new_req, "conditional_extras", conditional_extras)
        return new_req

    # PEP426 dict syntax
    # So only metadata that are of version 2.0 will be in dict. The other versions
    # (1.0, 1.1, 1.2, 2.1) will be strings.
    if isinstance(requirement, dict):
        result = []
        requires = requirement["requires"]
        extra = requirement.get("extra")
        marker_str = requirement.get("environment")

        # conditional extra, equivalent to: 'foo ; extra = "doc"'
        if extra:
            conditional_extras = set([extra])
        else:
            conditional_extras = None

        for req_str in requires:
            req = packaging_Requirement(req_str)
            new_req = reconstruct(req, marker_str, conditional_extras)
            result.append(new_req)

        return result

    # string-based syntax
    req = packaging_Requirement(requirement)

    # detect case: "mypkg ; extra == 'dev'"
    # note: packaging lib already delimits with whitespace
    marker_str = str(req.marker)
    marker_parts = marker_str.split()

    # already in PEP508, packaging lib- friendly format
    if "extra" not in marker_parts:
        setattr(req, "conditional_extras", None)
        return [req]

    # Parse conditional extras out of marker
    conditional_extras = set()
    marker_str = marker_str.replace(" and ", " \nand ")
    marker_str = marker_str.replace(" or ", " \nor ")
    lines = marker_str.split('\n')
    lines = [x.strip() for x in lines]
    new_marker_lines = []

    for line in lines:
        if "extra" in line.split():
            extra = line.split()[-1]
            extra = extra.replace('"', '')
            extra = extra.replace("'", '')
            conditional_extras.add(extra)
        else:
            new_marker_lines.append(line)

    # reconstruct requirement in new syntax
    if new_marker_lines:
        new_marker_parts = ' '.join(new_marker_lines).split()
        if new_marker_parts[0] in ("and", "or"):
            new_marker_parts = new_marker_parts[1:]
        new_marker_str = ' '.join(new_marker_parts)
    else:
        new_marker_str = ''

    new_req = reconstruct(req, new_marker_str, conditional_extras)
    return [new_req]
