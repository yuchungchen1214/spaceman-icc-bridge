"""Display Manager Pro-style appearance switching with native Qt controls."""

import re

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QPalette


APPEARANCE_DARK = "dark"
APPEARANCE_LIGHT = "light"
APPEARANCE_SYSTEM = "system"

DARK_STYLESHEET = """
QMainWindow { background-color: #1b1b1b; }
QMainWindow > QWidget { background-color: #1b1b1b; }
QLabel { color: #f2f2f2; }
QListWidget { background-color: #111111; }
QLineEdit, QTextEdit, QTableWidget {
    background-color: #111111;
    color: #f2f2f2;
}
"""


def appearance_hex(value, appearance):
    """Invert neutral grays for Light mode, preserving chromatic accents."""
    if appearance != APPEARANCE_LIGHT or not value.startswith("#"):
        return value
    digits = value[1:]
    if len(digits) == 3:
        channels = [int(digit * 2, 16) for digit in digits]
    elif len(digits) == 6:
        channels = [int(digits[index:index + 2], 16) for index in (0, 2, 4)]
    else:
        return value
    if channels[0] != channels[1] or channels[1] != channels[2]:
        return value
    inverse = 255 - channels[0]
    return f"#{inverse:02x}{inverse:02x}{inverse:02x}"


def appearance_stylesheet(appearance):
    return re.sub(
        r"#[0-9a-fA-F]{3,6}",
        lambda match: appearance_hex(match.group(0), appearance),
        DARK_STYLESHEET,
    )


def current_appearance_color(value):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    appearance = (app.property("bridgeActualAppearance")
                  if app is not None else APPEARANCE_DARK)
    return appearance_hex(value, appearance or APPEARANCE_DARK)


def _palette_for(app, appearance):
    palette = QPalette(app.palette())
    roles = {
        QPalette.ColorRole.Window: "#1b1b1b",
        QPalette.ColorRole.WindowText: "#f2f2f2",
        QPalette.ColorRole.Base: "#111111",
        QPalette.ColorRole.AlternateBase: "#1f1f1f",
        QPalette.ColorRole.ToolTipBase: "#222222",
        QPalette.ColorRole.ToolTipText: "#f2f2f2",
        QPalette.ColorRole.Text: "#f2f2f2",
        QPalette.ColorRole.Button: "#2d2d2d",
        QPalette.ColorRole.ButtonText: "#f2f2f2",
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: "#555555",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.Link: "#88a8c8",
        QPalette.ColorRole.PlaceholderText: "#888888",
    }
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, color in roles.items():
            palette.setColor(group, role, QColor(appearance_hex(color, appearance)))
    disabled = {
        QPalette.ColorRole.WindowText: "#777777",
        QPalette.ColorRole.Text: "#777777",
        QPalette.ColorRole.ButtonText: "#777777",
        QPalette.ColorRole.PlaceholderText: "#666666",
        QPalette.ColorRole.Button: "#242424",
    }
    for role, color in disabled.items():
        palette.setColor(QPalette.ColorGroup.Disabled, role,
                         QColor(appearance_hex(color, appearance)))
    return palette


class AppearanceController(QObject):
    modeChanged = Signal(str)
    actualAppearanceChanged = Signal(str)

    def __init__(self, app, settings):
        super().__init__(app)
        self.app = app
        self.settings = settings
        saved = str(settings.value("Appearance/Mode", APPEARANCE_SYSTEM)).lower()
        self.mode = saved if saved in {
            APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_SYSTEM
        } else APPEARANCE_SYSTEM
        self.actual = APPEARANCE_DARK
        self.set_mode(self.mode, save=False)
        self.app.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)

    def set_mode(self, mode, save=True):
        if mode not in {APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_SYSTEM}:
            return
        self.mode = mode
        if save:
            self.settings.setValue("Appearance/Mode", mode)
        self.modeChanged.emit(mode)
        requested = {
            APPEARANCE_DARK: Qt.ColorScheme.Dark,
            APPEARANCE_LIGHT: Qt.ColorScheme.Light,
            APPEARANCE_SYSTEM: Qt.ColorScheme.Unknown,
        }[mode]
        if self.app.styleHints().colorScheme() != requested or mode != APPEARANCE_SYSTEM:
            self.app.styleHints().setColorScheme(requested)
        self._apply_current_scheme()

    def _system_scheme_changed(self, _scheme):
        if self.mode == APPEARANCE_SYSTEM:
            self._apply_current_scheme()

    def _resolved_appearance(self):
        if self.mode != APPEARANCE_SYSTEM:
            return self.mode
        return (APPEARANCE_LIGHT
                if self.app.styleHints().colorScheme() == Qt.ColorScheme.Light
                else APPEARANCE_DARK)

    def _apply_current_scheme(self):
        previous = self.actual
        actual = self._resolved_appearance()
        self.app.setPalette(_palette_for(self.app, actual))
        self.app.setStyleSheet(appearance_stylesheet(actual))
        if previous != actual:
            self._transform_widget_styles(previous, actual)
        self.actual = actual
        self.app.setProperty("bridgeActualAppearance", actual)
        self.actualAppearanceChanged.emit(actual)

    def sync_widget_styles(self, root):
        """Theme per-widget QSS created after app startup from its dark base."""
        if self.actual == APPEARANCE_DARK:
            return
        self._transform_widget_styles(APPEARANCE_DARK, self.actual, root)

    def _transform_widget_styles(self, source, target, root=None):
        widgets = (root.findChildren(QObject) + [root]
                   if root is not None else self.app.allWidgets())
        for widget in widgets:
            if not hasattr(widget, "styleSheet"):
                continue
            stylesheet = widget.styleSheet()
            if stylesheet:
                widget.setStyleSheet(re.sub(
                    r"#[0-9a-fA-F]{3,6}",
                    lambda match: appearance_hex(match.group(0), target)
                    if source != target else match.group(0),
                    stylesheet,
                ))


def add_appearance_menu(window, controller):
    """Add Help > Appearance, matching Display Manager Pro's menu location."""
    help_menu = window.menuBar().addMenu("Help")
    appearance_menu = help_menu.addMenu("Appearance")
    group = QActionGroup(window)
    group.setExclusive(True)
    actions = {}
    for label, mode in (("Dark", APPEARANCE_DARK),
                        ("Light", APPEARANCE_LIGHT),
                        ("System", APPEARANCE_SYSTEM)):
        action = QAction(label, window)
        action.setCheckable(True)
        action.setData(mode)
        action.setToolTip("Follow the system appearance" if mode == APPEARANCE_SYSTEM
                          else f"Use {label.lower()} appearance")
        group.addAction(action)
        appearance_menu.addAction(action)
        action.triggered.connect(
            lambda _checked=False, selected=mode: controller.set_mode(selected))
        actions[mode] = action
    actions[controller.mode].setChecked(True)
    controller.modeChanged.connect(
        lambda selected: actions[selected].setChecked(True))
    return appearance_menu
