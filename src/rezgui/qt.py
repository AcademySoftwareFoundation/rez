"""
Abstraction for PyQt/PySide import.
"""
import sys
from rez.config import config


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
            USE_PYSIDE = False
        except ImportError:
            try:
                import PySide
                USE_PYSIDE = True
            except ImportError:
                raise Exception("rez gui tools require either PyQt4 or PySide; "
                                "neither package could be imported.")

if USE_PYSIDE:
    from PySide import QtGui, QtCore
else:
    from PyQt4 import QtGui, QtCore
    QtCore.Signal = QtCore.pyqtSignal
