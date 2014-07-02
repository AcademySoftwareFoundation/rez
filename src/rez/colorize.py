import logging
from rez.vendor import colorama
from rez.config import config


colorama.init()


def critical(str_):
    """ Return the string wrapped with the appropriate styling of a critical 
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """

    return color_level(str_, 'critical')


def error(str_):
    """ Return the string wrapped with the appropriate styling of an error 
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """

    return color_level(str_, 'error')


def warning(str_):
    """ Return the string wrapped with the appropriate styling of a warning 
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """

    return color_level(str_, 'warning')


def info(str_):
    """ Return the string wrapped with the appropriate styling of an info 
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """

    return color_level(str_, 'info')


def debug(str_):
    """ Return the string wrapped with the appropriate styling of a debug 
    message.  The styling will be determined based on the rez configuration.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """

    return color_level(str_, 'debug')


def notset(str_):
    """ Return the string wrapped with the appropriate escape sequences to 
    remove all styling.

    Args:
      str_ (str): The string to be wrapped.

    Returns:
      str: The string styled with the appropriate escape sequences.
    """

    return color(str_)


def color_level(str_, level):
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

    return color(str_, fore_color, back_color, styles)


def color(str_, fore_color=None, back_color=None, styles=None):
    """ Return the string wrapped with the appropriate styling escape sequences.

    Args:
      str_ (str): The string to be wrapped.
      fore_color (str, optional): Any foreground color supported by the `Colorama`_
        module.
      back_color (str, optional): Any background color supported by the `Colorama`_
        module.
      styles (list of str, optional): Any styles supported by the `Colorama`_ 
        module.

    Returns:
      str: The string styled with the appropriate escape sequences.

    .. _Colorama:
        https://pypi.python.org/pypi/colorama
    """

    colored = ""
    if not styles: styles = []

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


class ColorizedConsoleFormatter(logging.Formatter):
    """ A formatter for use with the Python logger.  This formatter uses the 
    `Colorama`_ module to style the log messages based on the rez configuration.

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
        0:  notset,
    }

    def __init__(self, fmt=None, datefmt=None):

        logging.Formatter.__init__(self, fmt=fmt, datefmt=datefmt)

    def _get_style_function_for_level(self, level):

        return self.STYLES.get(level, notset)

    def format(self, record):
        """ Extend the base implementation of this method to apply the 
        appropriate styling.
        """

        style = self._get_style_function_for_level(record.levelno)

        return style(logging.Formatter.format(self, record))
