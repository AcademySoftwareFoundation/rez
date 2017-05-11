"""
Abstraction for PyQt/PySide import.
"""
import os
import sys
from rez.config import config
from rez.exceptions import RezGuiQTImportError
from rez.utils.lint_helper import used


USE_PYSIDE = None
if config.use_pyside:
    if config.use_pyqt:
        from rez.exceptions import ConfigurationError
        raise ConfigurationError("'use_pyside' and 'use_pyqt' are both enabled")
    USE_PYSIDE = True
elif config.use_pyqt:
    USE_PYSIDE = False

if USE_PYSIDE is None:
    if 'PyQt4' in sys.modules:
        USE_PYSIDE = False
    elif 'PySide' in sys.modules:
        USE_PYSIDE = True
    else:
        try:
            import PyQt4
            used(PyQt4)
            USE_PYSIDE = False
        except ImportError:
            try:
                import PySide
                used(PySide)
                USE_PYSIDE = True
            except ImportError:
                raise RezGuiQTImportError(
                    "rez-gui requires either PyQt4 or PySide; "
                    "neither package could be imported.")

if USE_PYSIDE:
    from PySide import QtGui, QtCore
else:
    from PyQt4 import QtGui, QtCore
    QtCore.Signal = QtCore.pyqtSignal

used(QtCore)
used(QtGui)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
