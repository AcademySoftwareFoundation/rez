from rezgui.qt import QtCore, QtGui
from rez.util import readable_time_duration
import os.path
import time


def create_pane(widgets, horizontal, parent_widget=None, compact=False):
    """Create a widget containing an aligned set of widgets.

    Args:
        widgets (list of `QWidget`).
        horizontal (bool).
        align (str): One of:
            - 'left', 'right' (horizontal);
            - 'top', 'bottom' (vertical)
        parent_widget (`QWidget`): Owner widget, QWidget is created if this
            is not provided.

    Returns:
        `QWidget`
    """
    pane = parent_widget or QtGui.QWidget()
    type_ = QtGui.QHBoxLayout if horizontal else QtGui.QVBoxLayout
    layout = type_()
    if compact:
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)

    for widget in widgets:
        stretch = 0
        if isinstance(widget, tuple):
            widget, stretch = widget

        if isinstance(widget, int):
            layout.addSpacing(widget)
        elif widget:
            layout.addWidget(widget, stretch)
        else:
            layout.addStretch()

    pane.setLayout(layout)
    return pane


def create_toolbutton(entries, parent=None):
    """Create a toolbutton.

    Args:
        entries: List of (label, slot) tuples.

    Returns:
        `QtGui.QToolBar`.
    """
    btn = QtGui.QToolButton(parent)
    menu = QtGui.QMenu()
    actions = []

    for label, slot in entries:
        action = QtGui.QAction(label, btn)
        action.triggered.connect(slot)
        actions.append(action)
        menu.addAction(action)

    btn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
    btn.setDefaultAction(actions[0])
    btn.setMenu(menu)
    return btn


icons = {}


def get_icon(name):
    """Returns a `QPixmap` containing the given image."""
    filename = name + ".png"
    icon = icons.get(filename)
    if icon:
        return icon

    filepath = os.path.dirname(__file__)
    filepath = os.path.join(filepath, "icons", filename)
    icon = QtGui.QPixmap(filepath)
    icons[filename] = icon
    return icon


def get_icon_widget(filename, tooltip=None):
    icon = get_icon(filename)
    icon_label = QtGui.QLabel()
    icon_label.setPixmap(icon)
    if tooltip:
        icon_label.setToolTip(tooltip)
    return icon_label


def get_timestamp_str(timestamp):
    now = int(time.time())
    release_time = time.localtime(timestamp)
    release_time_str = time.strftime('%m %b %Y %H:%M', release_time)
    ago = readable_time_duration(now - timestamp)
    return "%s (%s ago)" % (release_time_str, ago)
