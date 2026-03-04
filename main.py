"""
main.py – Entry point for the Vending Machine application.

Usage:
    python main.py

First-time setup:
    pip install PyQt6 supabase
    python data/db_init.py   (creates the local SQLite database)
    python main.py
"""

import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont

# Bootstrap the DB if it doesn't exist yet
from data.db_init import init_db, DB_PATH

if not os.path.exists(DB_PATH):
    print("[main] Database not found – running first-time initialization…")
    init_db()

from core.state import StateManager
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Vending Machine")
    app.setApplicationDisplayName("Euro Vending Machine")

    # Set a clean default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Initialize state manager (loads from SQLite)
    try:
        sm = StateManager()
    except Exception as e:
        QMessageBox.critical(None, "Startup Error",
                             f"Failed to load database:\n{e}\n\n"
                             "Run:  python data/db_init.py  to reset the database.")
        sys.exit(1)

    window = MainWindow(sm)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
