"""
main_window.py – Main vending machine window (PyQt6).
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy, QMessageBox,
    QScrollArea, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

import sys
import os

# Ensure parent directory is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.state import StateManager, Product
from ui.coin_dialog import CoinInsertDialog
from ui.admin_panel import AdminPanel
from ui.styles import MAIN_STYLE, PRODUCT_BTN_STYLE, SCREEN_STYLE


class ProductButton(QPushButton):
    """A single product cell in the 3×3 grid."""

    def __init__(self, product: Product, parent=None):
        super().__init__(parent)
        self.product = product
        self._refresh(product)
        self.setFixedSize(QSize(140, 140))
        self.setStyleSheet(PRODUCT_BTN_STYLE)

    def _refresh(self, product: Product):
        self.product = product
        sold_out = product.stock == 0
        icon = product.emoji if not sold_out else "❌"
        self.setText(
            f"<div style='font-size:36px'>{icon}</div>"
            f"<div style='font-size:12px; font-weight:bold'>{product.name}</div>"
            f"<div style='font-size:11px; color:{'#e74c3c' if sold_out else '#27ae60'}'>"
            f"{'SOLD OUT' if sold_out else product.price_display}</div>"
        )
        self.setEnabled(not sold_out)

    def update_product(self, product: Product):
        self._refresh(product)


class DisplayScreen(QFrame):
    """The small LCD-style screen on the right panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SCREEN_STYLE)
        self.setFixedSize(QSize(220, 300))

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QLabel("🏪 VENDING MACHINE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #00ff41; font-size: 11px; font-weight: bold;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #00ff41;")
        layout.addWidget(sep)

        # Status message
        self.status_label = QLabel("Please choose\na product")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #00ff41; font-size: 13px;")
        layout.addWidget(self.status_label)

        # Inserted amount
        ins_row = QHBoxLayout()
        ins_row.addWidget(QLabel("Inserted:"))
        self.inserted_label = QLabel("€0.00")
        self.inserted_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        ins_row.addWidget(self.inserted_label)
        ins_widget = QWidget()
        ins_widget.setLayout(ins_row)
        ins_widget.setStyleSheet("color: #00ff41; font-size: 12px;")
        layout.addWidget(ins_widget)

        # Selected product
        self.selected_label = QLabel("")
        self.selected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_label.setWordWrap(True)
        self.selected_label.setStyleSheet("color: #ffff00; font-size: 12px;")
        layout.addWidget(self.selected_label)

        layout.addStretch()

        # Price to pay
        self.price_label = QLabel("")
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.price_label.setStyleSheet("color: #ff9900; font-size: 12px;")
        layout.addWidget(self.price_label)

    def set_status(self, msg: str):
        self.status_label.setText(msg)

    def set_inserted(self, cents: int):
        self.inserted_label.setText(f"€{cents/100:.2f}")

    def set_selected(self, product: Product | None):
        if product:
            self.selected_label.setText(f"{product.emoji} {product.name}")
            self.price_label.setText(f"Price: {product.price_display}")
        else:
            self.selected_label.setText("")
            self.price_label.setText("")


class MainWindow(QMainWindow):

    def __init__(self, state_manager: StateManager):
        super().__init__()
        self.sm = state_manager
        self.setWindowTitle("🏪 Euro Vending Machine")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(MAIN_STYLE)

        self._build_ui()
        self._refresh_all()

        # Blink timer for status message
        self._blink_timer = QTimer()
        self._blink_timer.timeout.connect(self._tick)
        self._blink_timer.start(500)
        self._blink_state = True

    # ─────────────────────────── UI Build ──────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Left: machine body ───────────────────────────────────────
        machine_frame = QFrame()
        machine_frame.setStyleSheet("""
            QFrame {
                background: #2c3e50;
                border-radius: 16px;
                border: 3px solid #7f8c8d;
            }
        """)
        machine_layout = QVBoxLayout(machine_frame)
        machine_layout.setSpacing(12)
        machine_layout.setContentsMargins(16, 16, 16, 16)

        # Brand header
        brand = QLabel("⚡ VENDOTRONIC 3000 ⚡")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("""
            color: #f39c12;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Courier New', monospace;
            letter-spacing: 2px;
        """)
        machine_layout.addWidget(brand)

        # Product grid
        grid_widget = QWidget()
        self.product_grid = QGridLayout(grid_widget)
        self.product_grid.setSpacing(8)

        self.product_buttons: dict[int, ProductButton] = {}
        products = list(self.sm.state.products.values())
        for i, product in enumerate(products[:9]):
            btn = ProductButton(product)
            btn.clicked.connect(lambda checked, pid=product.id: self._on_product_clicked(pid))
            self.product_grid.addWidget(btn, i // 3, i % 3)
            self.product_buttons[product.id] = btn

        machine_layout.addWidget(grid_widget)
        root.addWidget(machine_frame, stretch=3)

        # ── Right: control panel ─────────────────────────────────────
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # Display screen
        self.screen = DisplayScreen()
        right_panel.addWidget(self.screen)

        # Wallet balance
        self.wallet_label = QLabel()
        self.wallet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wallet_label.setStyleSheet("""
            background: #1a252f;
            color: #2ecc71;
            border: 1px solid #2ecc71;
            border-radius: 8px;
            padding: 6px;
            font-size: 13px;
            font-weight: bold;
        """)
        right_panel.addWidget(self.wallet_label)

        # Coin slot button
        coin_btn = QPushButton("🪙  INSERT COIN")
        coin_btn.setFixedHeight(48)
        coin_btn.setStyleSheet("""
            QPushButton {
                background: #e67e22;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #d35400; }
            QPushButton:pressed { background: #a04000; }
        """)
        coin_btn.clicked.connect(self._on_insert_coin)
        right_panel.addWidget(coin_btn)

        # Buy button
        self.buy_btn = QPushButton("✅  BUY")
        self.buy_btn.setFixedHeight(48)
        self.buy_btn.setEnabled(False)
        self.buy_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1e8449; }
            QPushButton:disabled {
                background: #566573;
                color: #aab7b8;
            }
        """)
        self.buy_btn.clicked.connect(self._on_buy)
        right_panel.addWidget(self.buy_btn)

        # Cancel / return coins
        cancel_btn = QPushButton("↩  CANCEL / RETURN")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #c0392b;
                color: white;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover { background: #a93226; }
        """)
        cancel_btn.clicked.connect(self._on_cancel)
        right_panel.addWidget(cancel_btn)

        right_panel.addStretch()

        # Admin button
        admin_btn = QPushButton("🔧  ADMIN")
        admin_btn.setFixedHeight(36)
        admin_btn.setStyleSheet("""
            QPushButton {
                background: #2c3e50;
                color: #95a5a6;
                border: 1px solid #7f8c8d;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #34495e;
                color: white;
            }
        """)
        admin_btn.clicked.connect(self._on_admin)
        right_panel.addWidget(admin_btn)

        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        right_widget.setFixedWidth(240)
        root.addWidget(right_widget)

    # ─────────────────────────── Event handlers ────────────────────────

    def _on_product_clicked(self, product_id: int):
        product = self.sm.state.products.get(product_id)
        if not product:
            return
        self.sm.state.selected_product = product
        self.screen.set_selected(product)
        inserted = self.sm.state.inserted_cents
        if inserted >= product.price_cents:
            self.screen.set_status(f"Press BUY for\n{product.name}!")
            self.buy_btn.setEnabled(True)
        else:
            needed = (product.price_cents - inserted) / 100
            self.screen.set_status(f"Insert €{needed:.2f}\nmore for {product.name}")
            self.buy_btn.setEnabled(False)

    def _on_insert_coin(self):
        dlg = CoinInsertDialog(self.sm, parent=self)
        dlg.coins_inserted.connect(self._on_coins_updated)
        dlg.exec()

    def _on_coins_updated(self):
        self._refresh_screen()
        self._refresh_wallet()
        # Re-check buy button
        p = self.sm.state.selected_product
        if p and self.sm.state.inserted_cents >= p.price_cents:
            self.buy_btn.setEnabled(True)
            self.screen.set_status(f"Press BUY for\n{p.name}!")
        elif p:
            needed = (p.price_cents - self.sm.state.inserted_cents) / 100
            self.screen.set_status(f"Insert €{needed:.2f}\nmore")

    def _on_buy(self):
        product = self.sm.state.selected_product
        if not product:
            return
        success, msg, change = self.sm.purchase_product(product.id)

        if success:
            change_str = ""
            if change:
                change_str = "\n\nChange returned:\n" + "\n".join(
                    f"  {cnt}x {self._denom_label(d)}"
                    for d, cnt in sorted(change.items(), reverse=True)
                )
            QMessageBox.information(self, "Purchase Complete",
                                    msg + change_str)
            self._refresh_all()
            self.buy_btn.setEnabled(False)
        else:
            self.screen.set_status(msg)
            QMessageBox.warning(self, "Cannot Purchase", msg)

    def _on_cancel(self):
        if self.sm.state.inserted_cents == 0 and not self.sm.state.selected_product:
            return
        returned = self.sm.cancel_transaction()
        if returned:
            lines = "\n".join(
                f"  {cnt}x {self._denom_label(d)}"
                for d, cnt in sorted(returned.items(), reverse=True)
            )
            QMessageBox.information(self, "Coins Returned",
                                    f"Returned to your wallet:\n{lines}")
        self._refresh_all()
        self.buy_btn.setEnabled(False)

    def _on_admin(self):
        panel = AdminPanel(self.sm, parent=self)
        panel.products_updated.connect(self._refresh_all)
        panel.exec()

    # ─────────────────────────── Refresh helpers ───────────────────────

    def _refresh_all(self):
        self.sm._load_all()
        self._refresh_products()
        self._refresh_screen()
        self._refresh_wallet()

    def _refresh_products(self):
        for pid, btn in self.product_buttons.items():
            product = self.sm.state.products.get(pid)
            if product:
                btn.update_product(product)

    def _refresh_screen(self):
        self.screen.set_inserted(self.sm.state.inserted_cents)
        self.screen.set_selected(self.sm.state.selected_product)

    def _refresh_wallet(self):
        total = self.sm.wallet_total_cents()
        self.wallet_label.setText(f"👛 Wallet: €{total/100:.2f}")

    def _tick(self):
        """Blink cursor on screen."""
        pass  # Could animate screen elements here

    def _denom_label(self, cents: int) -> str:
        labels = {1:"1ct",2:"2ct",5:"5ct",10:"10ct",20:"20ct",
                  50:"50ct",100:"€1.00",200:"€2.00"}
        return labels.get(cents, f"{cents}ct")
