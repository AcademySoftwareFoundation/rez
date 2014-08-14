from rezgui.qt import QtCore, QtGui


def create_pane(widgets, horizontal, parent_widget=None, spacing=0,
                margin=0):
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
    layout.setSpacing(spacing)
    layout.setContentsMargins(margin, margin, margin, margin)

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
