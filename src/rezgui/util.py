from rezgui.qt import QtGui
from rez.utils.formatting import readable_time_duration
import os.path
import time


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
    release_time_str = time.strftime('%d %b %Y %H:%M:%S', release_time)
    ago = readable_time_duration(now - timestamp)
    return "%s (%s ago)" % (release_time_str, ago)


def add_menu_action(menu, label, slot=None, icon_name=None, group=None,
                    parent=None):
    nargs = []
    if icon_name:
        icon = get_icon(icon_name, as_qicon=True)
        nargs.append(icon)
    nargs += [label, menu]
    if parent:
        nargs.append(parent)

    action = QtGui.QAction(*nargs)
    if slot:
        action.triggered.connect(slot)
    if group:
        action.setCheckable(True)
        group.addAction(action)
    menu.addAction(action)
    return action


def interp_color(a, b, f):
    """Interpolate between two colors.

    Returns:
        `QColor` object.
    """
    a_ = (a.redF(), a.greenF(), a.blueF())
    b_ = (b.redF(), b.greenF(), b.blueF())
    a_ = [x * (1 - f) for x in a_]
    b_ = [x * f for x in b_]
    c = [x + y for x, y in zip(a_, b_)]
    return QtGui.QColor.fromRgbF(*c)


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
        action = add_menu_action(menu, label, slot)
        actions.append(action)

    btn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
    btn.setDefaultAction(actions[0])
    btn.setMenu(menu)
    return btn, actions


def update_font(widget, italic=None, bold=None, underline=None):
    font = widget.font()
    if italic is not None:
        font.setItalic(italic)
    if bold is not None:
        font.setBold(bold)
    if underline is not None:
        font.setUnderline(underline)
    widget.setFont(font)


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
