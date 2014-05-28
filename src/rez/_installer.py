"""
Code used by the rez installation process. It's here because this enables it to
be used from two different places - from install.py (which developers use to do
a rez installation for testing purposes), and from the get-rez.py script, which
is a standalone rez installer, created using the build-installer.py script.
"""

def create_setup_cfg(install_path):
    """Create the content of a setup.cfg file for installing rez.

    Args:
        install_path (str): Path to install rez to. This is the base package
            path, ie rez will install to <PATH>/rez/<VERSION>/...

    Returns:
        Content of a setup.cfg file (str).
    """
    import textwrap
    from rez import __version__
    from rez.system import system

    content = textwrap.dedent( \
    """
    [install]
    install-base=%(base)s
    install-purelib=$base/rez/%(ver)s/%(os)s/python-$py_version_short/lib
    install-platlib=$base/rez/%(ver)s/%(os)s/python-$py_version_short/lib.$PLAT
    install-headers=$base/rez/%(ver)s/%(os)s/python-$py_version_short/headers
    install-scripts=$base/rez/%(ver)s/%(os)s/python-$py_version_short/bin
    install-data=$base
    """) % dict(base=install_path,
                ver=__version__,
                os=system.os)

    return content
