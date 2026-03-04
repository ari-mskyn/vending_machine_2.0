"""
coin_dialog.py – Coin insertion dialog (the coin slot).
Shows user's wallet and lets them click coins to insert.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.state import StateManager


COIN_META = {
    1:   ("1ct",   "#cd7f32"),   # copper
    2:   ("2ct",   "#cd7f32"),
    5:   ("5ct",   "#cd7f32"),
    10:  ("10ct",  "#c0c0c0"),   # silver
    20:  ("20ct",  "#c0c0c0"),
    50:  ("50ct",  "#c0c0c0"),
    100: ("€1",    "#ffd700"),   # gold
    200: ("€2",    "#ffd700"),
}


class CoinButton(QPushButton):
    def __init__(self, denom: int, count: int, parent=None):
        super().__init__(parent)
        self.denom = denom
        label, color = COIN_META.get(denom, (f"{denom}ct", "#aaa"))
        self._color = color
        self._label = label
        self._update(count)
        self.setFixedSize(72, 72)
        self._style(color, count > 0)

    def _update(self, count: int):
        self.setText(f"{self._label}\n×{count}")
        self._style(self._color, count > 0)

    def _style(self, color: str, enabled: bool):
        alpha = "ff" if enabled else "55"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {color}{alpha};
                border-radius: 36px;
                border: 3px solid #ffffff44;
                color: #1a1a1a;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border: 3px solid #ffffff99;
                background: {color};
            }}
            QPushButton:pressed {{
                background: {color}88;
            }}
            QPushButton:disabled {{
                color: #555;
            }}
        """)
        self.setEnabled(enabled)

    def refresh(self, count: int):
        self._update(count)


class CoinInsertDialog(QDialog):
    coins_inserted = pyqtSignal()

    def __init__(self, sm: StateManager, parent=None):
        super().__init__(parent)
        self.sm = sm
        self.setWindowTitle("🪙 Insert Coins")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet("""
            QDialog {
                background: #1a252f;
                color: white;
            }
            QLabel {
                color: white;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        hdr = QLabel("💰 Your Wallet – Click a coin to insert it")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(hdr)

        # Coin grid (2 rows × 4 coins)
        self.coin_buttons: dict[int, CoinButton] = {}
        grid = QGridLayout()
        grid.setSpacing(10)
        denoms = [1, 2, 5, 10, 20, 50, 100, 200]
        for i, d in enumerate(denoms):
            count = self.sm.state.wallet.get(d, 0)
            btn = CoinButton(d, count)
            btn.clicked.connect(lambda checked, denom=d: self._insert(denom))
            self.coin_buttons[d] = btn
            grid.addWidget(btn, i // 4, i % 4)
        layout.addLayout(grid)

        # Status bar
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(sep)

        status_row = QHBoxLayout()
        self.wallet_label = QLabel()
        self.inserted_label = QLabel()
        self.wallet_label.setStyleSheet("color: #2ecc71; font-size: 12px;")
        self.inserted_label.setStyleSheet("color: #f39c12; font-size: 12px;")
        status_row.addWidget(self.wallet_label)
        status_row.addStretch()
        status_row.addWidget(self.inserted_label)
        layout.addLayout(status_row)
        self._refresh_labels()

        # Done button
        done_btn = QPushButton("✅  Done")
        done_btn.setFixedHeight(40)
        done_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1e8449; }
        """)
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn)

    def _insert(self, denom: int):
        if self.sm.insert_coin(denom):
            # Update button count
            new_count = self.sm.state.wallet.get(denom, 0)
            self.coin_buttons[denom].refresh(new_count)
            self._refresh_labels()
            self.coins_inserted.emit()

    def _refresh_labels(self):
        wallet_total = self.sm.wallet_total_cents()
        inserted = self.sm.state.inserted_cents
        self.wallet_label.setText(f"👛 Wallet: €{wallet_total/100:.2f}")
        self.inserted_label.setText(f"🪙 Inserted: €{inserted/100:.2f}")
