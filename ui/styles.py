"""styles.py – Global QSS stylesheets."""

MAIN_STYLE = """
    QMainWindow {
        background: #0d1117;
    }
    QWidget {
        background: #0d1117;
        color: #e6edf3;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QScrollBar:vertical {
        background: #161b22;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #3d444d;
        border-radius: 4px;
    }
"""

PRODUCT_BTN_STYLE = """
    QPushButton {
        background: #161b22;
        border: 2px solid #30363d;
        border-radius: 12px;
        color: #e6edf3;
        text-align: center;
        padding: 8px;
    }
    QPushButton:hover {
        background: #1f2937;
        border: 2px solid #58a6ff;
    }
    QPushButton:pressed {
        background: #0d419d;
        border: 2px solid #1f6feb;
    }
    QPushButton:disabled {
        background: #0d1117;
        border: 2px solid #21262d;
        color: #484f58;
    }
    QPushButton:checked {
        background: #0d419d;
        border: 2px solid #388bfd;
    }
"""

SCREEN_STYLE = """
    QFrame {
        background: #0a1628;
        border: 3px solid #00ff41;
        border-radius: 8px;
    }
    QLabel {
        background: transparent;
        font-family: 'Courier New', monospace;
        color: #00ff41;
    }
"""
