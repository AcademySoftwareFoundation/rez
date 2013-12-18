"""
Exceptions.
Note: Every exception class can be default-constructed (ie all args default to None) because of
a serialisation issue with the exception class, see:
http://irmen.home.xs4all.nl/pyro3/troubleshooting.html
"""


class RezError(Exception):
    """
    Base-class Rez error.
    """
    def __init__(self, value=None):
        self.value = value

    def __str__(self):
        return str(self.value)


class PkgSystemError(RezError):
    """
    rez system error
    """
    def __init__(self, value):
        RezError.__init__(self, value)


class PkgFamilyNotFoundError(RezError):
    """
    A package family could not be found
    """
    def __init__(self, family_name=None):
        RezError.__init__(self)
        self.family_name = family_name

    def __str__(self):
        return str(self.family_name)


class PkgNotFoundError(RezError):
    """
    A package could not be found
    """
    def __init__(self, pkg_req=None, resolve_path=None):
        RezError.__init__(self)
        self.pkg_req = pkg_req
        self.resolve_path = resolve_path

    def __str__(self):
        return str((str(self.pkg_req), self.resolve_path))


class PkgConflictError(RezError):
    """
    A package conflicts with another. A list of conflicts is provided -
    this is for cases where all of a package's variants conflict with various
    packages
    """
    def __init__(self, pkg_conflicts=None, last_dot_graph=""):
        RezError.__init__(self)
        self.pkg_conflicts = pkg_conflicts
        self.last_dot_graph = last_dot_graph

    def __str__(self):
        return '\n' + '\n'.join([str(x) for x in self.pkg_conflicts])


class PkgsUnresolvedError(RezError):
    """
    One or more packages are not resolved
    """
    def __init__(self, pkg_reqs=None):
        RezError.__init__(self)
        self.pkg_reqs = pkg_reqs

    def __str__(self):
        strs = []
        for pkg_req in self.pkg_reqs:
            strs.append(str(pkg_req))
        return str(strs)


class PkgConfigNotResolvedError(RezError):
    """
    The configuration could not be resolved. 'fail_config_list' is a list of
    strings indicating failed configuration attempts.
    """
    def __init__(self, pkg_reqs=None, fail_config_list=None, last_dot_graph=None):
        RezError.__init__(self)
        self.pkg_reqs = pkg_reqs
        self.fail_config_list = fail_config_list
        self.last_dot_graph = last_dot_graph

    def __str__(self):
        strs = []
        for pkg_req in self.pkg_reqs:
            strs.append(str(pkg_req))
        return str(strs)


class PkgCommandError(RezError):
    """
    There is an error in a command or list of commands
    """
    def __init__(self, value=None):
        RezError.__init__(self, value)


class PkgCyclicDependency(RezError):
    """
    One or more cyclic dependencies have been detected in a set of packages
    """
    def __init__(self, dependencies=None, dot_graph=None):
        """
        dependencies is a list of (requiree, required) pairs.
        dot_graph_str is a string describing the dot-graph of the whole environment resolution -
        it is required because the user will want to have context, to determine how the cyclic
        list of packages was generated in the first place
        """
        RezError.__init__(self)
        self.deps = dependencies
        self.dot_graph = dot_graph

    def __str__(self):
        # print out as a dot-graph
        s = "digraph g {\n"
        for dep in self.deps:
            s += '"' + dep[0] + '" -> "' + dep[1] + '"\n'
        s += "}"
        return s













#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
