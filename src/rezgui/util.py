from rezgui.qt import QtCore, QtGui
from rez.util import readable_time_duration, OrderedDict
import os.path
import time


lock_types = OrderedDict([
    ("lock_2",  "minor version updates only (rank 2)"),
    ("lock_3",  "patch version updates only (rank 3)"),
    ("lock_4",  "build version updates only (rank 4)"),
    ("lock",    "exact version")])


def create_pane(widgets, horizontal, parent_widget=None, compact=False,
                compact_spacing=2):
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
        layout.setSpacing(compact_spacing)
        layout.setContentsMargins(compact_spacing, compact_spacing,
                                  compact_spacing, compact_spacing)

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
    return btn, actions


icons = {}


def get_icon(name, as_qicon=False):
    """Returns a `QPixmap` containing the given image, or a QIcon if `as_qicon`
    is True"""
    filename = name + ".png"
    icon = icons.get(filename)
    if not icon:
        path = os.path.dirname(__file__)
        path = os.path.join(path, "icons")
        filepath = os.path.join(path, filename)
        if not os.path.exists(filepath):
            filepath = os.path.join(path, "pink.png")

        icon = QtGui.QPixmap(filepath)
        icons[filename] = icon

    return QtGui.QIcon(icon) if as_qicon else icon


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
