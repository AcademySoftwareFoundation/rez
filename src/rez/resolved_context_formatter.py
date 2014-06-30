from rez.vendor.colorama import init
from rez.vendor.colorama import Fore
from rez.vendor.colorama import Style
from rez.util import columnise, is_subdirectory
from rez.settings import settings
import os
import time


class ResolvedContextFormatter(object):
    """ A formatter for resolved contexts.  A formatter will except a resolved
    context object and return a string representation for human consumption.
    """

    def __init__(self, resolved_context):
        """ Create a formatter.

        Args:
            resolved_context: An instance of rez.resolved_context.ResolvedContext.
        """

        self.resolved_context = resolved_context

    def _format_time(self, time_to_format, include_timestamp=False):
        """ Format the supplied timestamp in a human friendly manner.

        Args:
            time_to_format: timestamp representing the time to be formatted.
            include_timestamp: bool.  Set to True to include the original 
                unformatted timestamp in the result.

        Returns:
            String.
        """

        strftime = time.strftime("%a %b %d %H:%M:%S %Z %Y", time.localtime(time_to_format))

        if include_timestamp:
            strftime += " (%s)" % int(time_to_format)

        return strftime

    def _is_pkg_implicit(self, pkg):
        """ Was the package implicit at the time of the resolve?

        Args:
            pkg: An instance of rez.packages.Variant.

        Returns:
            Bool.
        """

        implicit_package_names = [ipkg.name for ipkg in self.resolved_context.implicit_packages]

        return pkg.name in implicit_package_names

    def _get_tokens(self, pkg):
        """ Get a list of string tokens for the resolved package.

        Args:
            pkg: An instance of rez.packages.Variant.

        Returns:
            A list of strings.
        """

        tokens = []

        if not os.path.exists(pkg.root):
            tokens.append('NOT FOUND')

        if is_subdirectory(pkg.root, settings.local_packages_path):
            tokens.append('local')

        if self._is_pkg_implicit(pkg):
            tokens.append('implicit')

        return tokens

    def _get_tokens_string(self, pkg):
        """ Get the string representation of a list of tokens for the provided 
        package.

        Args:
            pkg: An instance of rez.packages.Variant.

        Returns:
            A comma separated string of tags surrounded by brackets.  If no 
            tokens are found, an empty string.
        """

        tokens = self._get_tokens(pkg)

        if tokens:
            return "(%s)" % ",".join(tokens)

        return ""

    def format(self, verbose):
        """ Return a string to provide information about the resolved context 
        in a human friendly manner.

        Args:
            verbose: If True, include more information about the resolved 
                context.

        Returns:
            A string correctly formatted for writing to a buffer (such as 
            sys.stdout).
        """

        raise NotImplementedError


class SimpleResolvedContextFormatter(ResolvedContextFormatter):
    """ A formatter for resolved contexts.  A formatter will except a resolved
    context object and return a string representation for human consumption.
    
    This class is a plain text representation of the context, without 
    decoration.
    """

    def format(self, verbose):
        """ Return a string to provide information about the resolved context 
        in a human friendly manner.

        Args:
            verbose: If True, include more information about the resolved 
                context.

        Returns:
            A string correctly formatted for writing to a buffer (such as 
            sys.stdout).
        """

        str_ = ""

        if self.resolved_context.status in ("failed", "aborted"):
            str_ += "The context failed to resolve:\n"
            str_ += self.resolved_context.failure_description
            return str_

        t_str = self._format_time(self.resolved_context.created, include_timestamp=verbose)
        str_ += "resolved by %s@%s, on %s, using Rez v%s\n" \
            % (self.resolved_context.user, self.resolved_context.host, t_str, self.resolved_context.rez_version)
        if self.resolved_context.timestamp:
            t_str = self._format_time(self.resolved_context.timestamp, include_timestamp=verbose)
            str_ += "packages released after %s were ignored\n" % t_str
        str_ += "\n"

        if verbose:
            str_ += "search paths:\n"
            for path in self.resolved_context.package_paths:
                str_ += path + "\n"
            str_ += "\n"

        str_ += "requested packages:\n"
        for pkg in self.resolved_context.package_requests:
            str_ += str(pkg) + "\n"
        str_ += "\n"

        str_ += "local packages:\n"
        for pkg in self.resolved_context.resolved_packages:
            if pkg.is_local:
                str_ += pkg.qualified_package_name + "\n"
        str_ += "\n"

        str_ += "resolved packages:\n"
        rows = []
        for pkg in (self.resolved_context.resolved_packages or []):
            tok = self._get_tokens_string(pkg)
            rows.append((pkg.qualified_package_name, pkg.root, tok))
        str_ += '\n'.join(columnise(rows))

        if verbose:
            str_ += "\n"
            str_ += "resolve details:"
            str_ += "load time: %.02f secs" % self.resolved_context.load_time
            # solve time includes load time
            str_ += "solve time: %.02f secs" % (self.resolved_context.solve_time - self.resolved_context.load_time)

        return str_


class ColorizedResolvedContextFormatter(ResolvedContextFormatter):
    """ A formatter for resolved contexts.  A formatter will except a resolved
    context object and return a string representation for human consumption.
    
    This class is a plain text representation of the context using terminal 
    escape sequences to colour and highlight particular sections.
    """

    def _bright(self, s):
        """ Wrap the supplied string in bright/bold markup.
        """

        return Style.BRIGHT + s + Style.RESET_ALL

    def _dim(self, s):
        """ Wrap the supplied string in dim markup.
        """

        return Style.DIM + s + Style.RESET_ALL

    def _red(self, s):
        """ Wrap the supplied string in red markup.
        """

        return Fore.RED + s + Fore.RESET

    def _cyan(self, s):
        """ Wrap the supplied string in cyan markup.
        """

        return Fore.CYAN + s + Fore.RESET

    def _green(self, s):
        """ Wrap the supplied string in green markup.
        """

        return Fore.GREEN + s + Fore.RESET

    def format(self, verbose):
        """ Return a string to provide information about the resolved context 
        in a human friendly manner.

        Args:
            verbose: If True, include more information about the resolved 
                context.

        Returns:
            A string correctly formatted for writing to a buffer (such as 
            sys.stdout).
        """

        init()

        str_ = ""

        if self.resolved_context.status in ("failed", "aborted"):
            str_ += self._red(self._bright("The context failed to resolve:\n"))
            str_ += self._red(str(self.resolved_context.failure_description))
            return str_

        t_str = self._format_time(self.resolved_context.created, include_timestamp=verbose)
        str_ += "resolved by %s@%s, on %s, using Rez v%s\n" \
            % (self._bright(self.resolved_context.user), self._bright(self.resolved_context.host), self._bright(t_str), self._bright(self.resolved_context.rez_version))
        if self.resolved_context.timestamp:
            t_str = self._format_time(self.resolved_context.timestamp, include_timestamp=verbose)
            str_ += self._red("packages released after ") + self._red(self._bright(t_str)) + self._red(" were ignored\n")
        str_ += "\n"

        if verbose:
            str_ += self._bright("search paths:\n")
            for path in self.resolved_context.package_paths:
                str_ += path + "\n"
            str_ += "\n"

        str_ += self._bright("requested packages:\n")
        for pkg in self.resolved_context.package_requests:
            if pkg in self.resolved_context.implicit_packages:
                str_ += self._cyan(str(pkg)) + "\n"
            else:
                str_ += str(pkg) + "\n"
        str_ += "\n"

        str_ += self._bright("local packages:\n")
        for pkg in self.resolved_context.resolved_packages:
            if pkg.is_local:
                str_ += self._green(pkg.qualified_package_name) + "\n"
        str_ += "\n"

        str_ += self._bright("resolved packages:\n")

        rows = []
        for pkg in (self.resolved_context.resolved_packages or []):
            tok = self._get_tokens_string(pkg)
            rows.append((pkg.qualified_package_name, pkg.root, tok))

        for row in columnise(rows):
            if 'NOT FOUND' in str(row):
                str_ += self._red(str(row)) + '\n'
            elif 'local' in str(row):
                str_ += self._green(str(row)) + '\n'
            elif 'implicit' in str(row):
                str_ += self._cyan(str(row)) + '\n'
            else:
                str_ += str(row) + '\n'

        if verbose:
            str_ += "\n"
            str_ += self._bright("resolve details:")
            str_ += "load time: %.02f secs" % self.resolved_context.load_time
            # solve time includes load time
            str_ += "solve time: %.02f secs" % (self.resolved_context.solve_time - self.resolved_context.load_time)

        return str_

