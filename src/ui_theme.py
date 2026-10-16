"""Fixed UI colors while preserving the platform's native widget style."""

from PySide6.QtGui import QColor, QPalette


def apply_fixed_surface_colors(app):
    # Tint native buttons without replacing their platform style or geometry.
    palette = QPalette(app.palette())
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        palette.setColor(group, QPalette.ColorRole.Button, QColor("#2d2d2d"))
        palette.setColor(group, QPalette.ColorRole.ButtonText, QColor("#f2f2f2"))
        palette.setColor(group, QPalette.ColorRole.Highlight, QColor("#555555"))
        palette.setColor(group, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button,
                     QColor("#242424"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
                     QColor("#777777"))
    app.setPalette(palette)

    # Match display-manager-pro's dark surfaces. No QPushButton selectors,
    # stylesheet borders, padding, or radius: native button shapes stay intact.
    app.setStyleSheet("""
        QMainWindow { background-color: #1b1b1b; }
        QMainWindow > QWidget { background-color: #1b1b1b; }
        QLabel { color: #f2f2f2; }
        QListWidget { background-color: #111111; }
        QLineEdit, QTextEdit, QTableWidget {
            background-color: #111111;
            color: #f2f2f2;
        }
    """)
