# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import print_function

import sys
import logging
from rez.vendor import colorama
from rez.config import config


_initialised = False


def _init_colorama():
    global _initialised
    if not _initialised:
        colorama.init()
        _initialised = True


def stream_is_tty(stream):
    """Return true if the stream is a tty stream.

    Returns:
        bool
    """
    isatty = getattr(stream, 'isatty', None)
    return isatty and isatty()


def critical(str_):
    """ Return the string wrapped with the appropriate styling of a critical
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'critical')


def error(str_):
    """ Return the string wrapped with the appropriate styling of an error
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'error')


def warning(str_):
    """ Return the string wrapped with the appropriate styling of a warning
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'warning')


def info(str_):
    """ Return the string wrapped with the appropriate styling of an info
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'info')


def debug(str_):
    """ Return the string wrapped with the appropriate styling of a debug
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'debug')


def heading(str_):
    """ Return the string wrapped with the appropriate styling of a heading
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'heading')


def local(str_):
    """ Return the string wrapped with the appropriate styling to display a
    local package.  The styling will be determined based on the rez
    configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'local')


def implicit(str_):
    """ Return the string wrapped with the appropriate styling to display an
    implicit package.  The styling will be determined based on the rez
    configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'implicit')


def ephemeral(str_):
    """ Return the string wrapped with the appropriate styling to display an
    ephemeral package.  The styling will be determined based on the rez
    configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'ephemeral')


def alias(str_):
    """ Return the string wrapped with the appropriate styling to display a
    tool alias.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color_level(str_, 'alias')


def inactive(str_):
    """Return the string wrapped with the appropriate styling to display
    something inactive.

    Choices are grey, grey or grey.
    """
    return _color(str_, styles=["DIM"])


def notset(str_):
    """ Return the string wrapped with the appropriate escape sequences to
    remove all styling.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    return _color(str_)


def _color_level(str_, level):
    """ Return the string wrapped with the appropriate styling for the message
    level.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.
      level (str): The message level. Should be one of 'critical', 'error',
        'warning', 'info' or 'debug'.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """
    fore_color, back_color, styles = _get_style_from_config(level)
    return _color(str_, fore_color, back_color, styles)


def _color(str_, fore_color=None, back_color=None, styles=None):
    """ Return the string wrapped with the appropriate styling escape sequences.

    Args:
      str_ (str): The string to be wrapped.
      fore_color (str, optional): Any foreground color supported by the
        `Colorama`_ module.
      back_color (str, optional): Any background color supported by the
        `Colorama`_ module.
      styles (list of str, optional): Any styles supported by the `Colorama`_
        module.

    Returns:
      str: The string styled with the appropriate escape sequences.

    .. _Colorama:
        https://pypi.python.org/pypi/colorama
    """
    if not config.get("color_enabled", False):
        return str_

    # lazily init colorama. This is important - we don't want to init at startup,
    # because colorama prints a RESET_ALL character atexit. This in turn adds
    # unexpected output when capturing the output of a command run in a
    # ResolvedContext, for example.
    _init_colorama()

    colored = ""
    if not styles:
        styles = []

    if fore_color:
        colored += getattr(colorama.Fore, fore_color.upper(), '')
    if back_color:
        colored += getattr(colorama.Back, back_color.upper(), '')
    for style in styles:
        colored += getattr(colorama.Style, style.upper(), '')

    return colored + str_ + colorama.Style.RESET_ALL


def _get_style_from_config(key):
    fore_color = config.get("%s_fore" % key, '')
    back_color = config.get("%s_back" % key, '')
    styles = config.get("%s_styles" % key, None)
    return fore_color, back_color, styles


class ColorizedStreamHandler(logging.StreamHandler):
    """A stream handler for use with the Python logger.

    This handler uses the `Colorama`_ module to style the log messages based
    on the rez configuration.

    Attributes:
      STYLES (dict): A mapping between the Python logger levels and a function
        that can be used to provide the appropriate styling.

    .. _Colorama:
        https://pypi.python.org/pypi/colorama
    """
    STYLES = {
        50: critical,
        40: error,
        30: warning,
        20: info,
        10: debug,
        0: notset,
    }

    @property
    def is_tty(self):
        """Return true if the stream associated with this handler is a tty
        stream.

        Returns:
            bool
        """
        return stream_is_tty(self.stream)

    @property
    def is_colorized(self):
        return config.get("color_enabled", False) == "force" or self.is_tty

    def _get_style_function_for_level(self, level):
        return self.STYLES.get(level, notset)

    def emit(self, record):
        """Emit a record.

        If the stream associated with this handler provides tty then the record
        that is emitted with be formatted to include escape sequences for
        appropriate styling.
        """
        try:
            message = self.format(record)

            if not self.is_colorized:
                self.stream.write(message)
            else:
                style = self._get_style_function_for_level(record.levelno)
                self.stream.write(style(message))

            self.stream.write(getattr(self, 'terminator', '\n'))
            self.flush()

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class Printer(object):
    def __init__(self, buf=sys.stdout):
        self.buf = buf
        self.colorize = (
            config.get("color_enabled", False) == "force"
            or stream_is_tty(buf)
        )

    def __call__(self, msg='', style=None):
        print(self.get(msg, style), file=self.buf)
        if hasattr(self.buf, 'flush'):
            self.buf.flush()

    def get(self, msg, style=None):
        if style and self.colorize:
            msg = style(msg)
        return msg
