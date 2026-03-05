"""
admin_panel.py – Admin panel (PIN-protected) with:
  - Inventory overview + low-stock alerts
  - Product refill
  - Coin inventory management (add/withdraw)
  - Transaction log
  - Supabase sync
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QLineEdit, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFrame,
    QScrollArea, QDoubleSpinBox, QGridLayout, QGroupBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.state import StateManager, Product


COIN_META = {
    1:   "1 ct",  2:  "2 ct",  5:  "5 ct",  10: "10 ct",
    20: "20 ct",  50: "50 ct", 100: "€1.00", 200: "€2.00",
}

ADMIN_STYLE = """
    QDialog { background: #1c2833; color: #ecf0f1; }
    QTabWidget::pane { border: 1px solid #2c3e50; background: #1c2833; }
    QTabBar::tab {
        background: #2c3e50; color: #bdc3c7;
        padding: 8px 16px; border-radius: 4px 4px 0 0;
    }
    QTabBar::tab:selected { background: #3498db; color: white; }
    QLabel { color: #ecf0f1; }
    QLineEdit, QSpinBox, QDoubleSpinBox {
        background: #2c3e50; color: white;
        border: 1px solid #7f8c8d; border-radius: 4px;
        padding: 4px;
    }
    QTableWidget {
        background: #1a252f; color: #ecf0f1;
        gridline-color: #2c3e50;
        border: 1px solid #2c3e50;
    }
    QHeaderView::section {
        background: #2c3e50; color: white;
        padding: 6px; border: none;
    }
    QGroupBox {
        border: 1px solid #3498db;
        border-radius: 6px;
        margin-top: 8px;
        color: #3498db;
        font-weight: bold;
    }
    QGroupBox::title { subcontrol-origin: margin; padding: 0 4px; }
"""


class PinDialog(QDialog):
    """PIN entry gate before admin access."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔐 Admin Login")
        self.setModal(True)
        self.setFixedSize(300, 160)
        self.setStyleSheet(ADMIN_STYLE)
        self.pin_value = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Enter Admin PIN:"))
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setPlaceholderText("●●●●")
        self.pin_input.returnPressed.connect(self._submit)
        layout.addWidget(self.pin_input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c;")
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Login")
        ok.setStyleSheet("background: #3498db; color: white; border-radius: 4px; padding: 6px 16px;")
        ok.clicked.connect(self._submit)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def _submit(self):
        self.pin_value = self.pin_input.text()
        self.accept()


class AdminPanel(QDialog):
    products_updated = pyqtSignal()

    def __init__(self, sm: StateManager, parent=None):
        super().__init__(parent)
        self.sm = sm
        self.setWindowTitle("🔧 Admin Panel")
        self.setModal(True)
        self.setMinimumSize(700, 550)
        self.setStyleSheet(ADMIN_STYLE)

        if not self._authenticate():
            # Close on next event loop tick
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self.reject)
            return

        self.sm.enter_admin_mode()
        self._build_ui()
        self._refresh_all()

    def _authenticate(self) -> bool:
        dlg = PinDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        if self.sm.verify_admin_pin(dlg.pin_value):
            return True
        QMessageBox.critical(self, "Access Denied", "Incorrect PIN.")
        return False

    def closeEvent(self, event):
        self.sm.exit_admin_mode()
        super().closeEvent(event)

    # ─────────────────────────── UI build ──────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header with alert banner
        self.alert_banner = QLabel()
        self.alert_banner.setWordWrap(True)
        self.alert_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alert_banner.setStyleSheet("""
            background: #c0392b; color: white;
            font-weight: bold; padding: 8px;
            border-radius: 6px;
        """)
        self.alert_banner.hide()
        layout.addWidget(self.alert_banner)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_inventory_tab(), "📦 Inventory")
        tabs.addTab(self._build_coins_tab(), "🪙 Coins")
        tabs.addTab(self._build_products_tab(), "✏️ Products")
        tabs.addTab(self._build_log_tab(), "📋 Log")
        tabs.addTab(self._build_sync_tab(), "☁️ Supabase Sync")

        # Close button
        close_btn = QPushButton("🔒 Exit Admin Mode")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #c0392b; color: white;
                border-radius: 6px; padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #a93226; }
        """)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    # ─────────────────────────── Inventory tab ─────────────────────────

    def _build_inventory_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        info = QLabel("Refill individual products. ⚠ = low stock, ❌ = out of stock.")
        info.setStyleSheet("color: #95a5a6; font-size: 11px;")
        layout.addWidget(info)

        self.inv_table = QTableWidget(0, 5)
        self.inv_table.setHorizontalHeaderLabels(
            ["#", "Product", "Price", "Stock", "Refill"]
        )
        self.inv_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.inv_table)

        # Summary row
        self.inv_summary = QLabel()
        self.inv_summary.setStyleSheet("color: #bdc3c7; font-size: 12px;")
        layout.addWidget(self.inv_summary)

        return w

    def _populate_inventory_tab(self):
        products = list(self.sm.state.products.values())
        self.inv_table.setRowCount(len(products))
        for row, p in enumerate(products):
            # ID
            self.inv_table.setItem(row, 0, QTableWidgetItem(str(p.id)))

            # Name + emoji
            name_item = QTableWidgetItem(f"{p.emoji} {p.name}")
            self.inv_table.setItem(row, 1, name_item)

            # Price
            self.inv_table.setItem(row, 2, QTableWidgetItem(p.price_display))

            # Stock with color
            stock_item = QTableWidgetItem(str(p.stock))
            stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p.stock == 0:
                stock_item.setForeground(QColor("#e74c3c"))
                stock_item.setText("0 ❌")
            elif p.stock <= 3:
                stock_item.setForeground(QColor("#f39c12"))
                stock_item.setText(f"{p.stock} ⚠")
            else:
                stock_item.setForeground(QColor("#2ecc71"))
            self.inv_table.setItem(row, 3, stock_item)

            # Refill button + spinner in a widget
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(2, 2, 2, 2)
            spinner = QSpinBox()
            spinner.setMinimum(1)
            spinner.setMaximum(50)
            spinner.setValue(5)
            btn = QPushButton("➕ Add")
            btn.setStyleSheet("""
                QPushButton {
                    background: #27ae60; color: white;
                    border-radius: 4px; padding: 3px 8px;
                }
                QPushButton:hover { background: #1e8449; }
            """)
            btn.clicked.connect(
                lambda checked, pid=p.id, sp=spinner: self._refill_product(pid, sp.value())
            )
            cell_layout.addWidget(spinner)
            cell_layout.addWidget(btn)
            self.inv_table.setCellWidget(row, 4, cell)

        # Summary
        summary = self.sm.get_inventory_summary()
        low = summary["low_stock"]
        out = summary["out_of_stock"]
        parts = []
        if out:
            parts.append(f"❌ Out of stock: {', '.join(p.name for p in out)}")
        if low:
            parts.append(f"⚠ Low stock: {', '.join(p.name for p in low)}")
        self.inv_summary.setText("  |  ".join(parts) if parts else "✅ All products well-stocked")

        # Alert banner
        if summary["needs_attention"]:
            msgs = []
            if out:
                msgs.append(f"OUT OF STOCK: {', '.join(p.name for p in out)}")
            if low:
                msgs.append(f"LOW STOCK: {', '.join(f'{p.name} ({p.stock})' for p in low)}")
            self.alert_banner.setText("⚠  " + "   |   ".join(msgs))
            self.alert_banner.show()
        else:
            self.alert_banner.hide()

    def _refill_product(self, product_id: int, qty: int):
        self.sm.admin_refill_product(product_id, qty)
        self._refresh_all()
        self.products_updated.emit()

    # ─────────────────────────── Coins tab ─────────────────────────────

    def _build_coins_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Total coin value
        self.coin_total_label = QLabel()
        self.coin_total_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #f39c12;")
        layout.addWidget(self.coin_total_label)

        self.coin_table = QTableWidget(0, 4)
        self.coin_table.setHorizontalHeaderLabels(
            ["Denomination", "Count in Machine", "Add Coins", "Withdraw"]
        )
        self.coin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.coin_table.verticalHeader().setVisible(False)
        self.coin_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.coin_table)

        return w

    def _populate_coins_tab(self):
        denoms = sorted(self.sm.state.coin_inventory.keys(), reverse=True)
        self.coin_table.setRowCount(len(denoms))

        total = 0
        for row, denom in enumerate(denoms):
            count = self.sm.state.coin_inventory.get(denom, 0)
            total += denom * count

            self.coin_table.setItem(row, 0,
                QTableWidgetItem(COIN_META.get(denom, f"{denom}ct")))
            self.coin_table.setItem(row, 1, QTableWidgetItem(str(count)))

            # Add widget
            add_cell = QWidget()
            add_layout = QHBoxLayout(add_cell)
            add_layout.setContentsMargins(2, 2, 2, 2)
            add_spin = QSpinBox(); add_spin.setMinimum(1); add_spin.setMaximum(100); add_spin.setValue(10)
            add_btn = QPushButton("➕")
            add_btn.setStyleSheet("background:#27ae60;color:white;border-radius:3px;padding:3px;")
            add_btn.clicked.connect(
                lambda checked, d=denom, sp=add_spin: self._add_coins(d, sp.value())
            )
            add_layout.addWidget(add_spin); add_layout.addWidget(add_btn)
            self.coin_table.setCellWidget(row, 2, add_cell)

            # Withdraw widget
            wd_cell = QWidget()
            wd_layout = QHBoxLayout(wd_cell)
            wd_layout.setContentsMargins(2, 2, 2, 2)
            wd_spin = QSpinBox(); wd_spin.setMinimum(1); wd_spin.setMaximum(max(1, count)); wd_spin.setValue(min(5, max(1, count)))
            wd_btn = QPushButton("➖")
            wd_btn.setStyleSheet("background:#c0392b;color:white;border-radius:3px;padding:3px;")
            wd_btn.setEnabled(count > 0)
            wd_btn.clicked.connect(
                lambda checked, d=denom, sp=wd_spin: self._withdraw_coins(d, sp.value())
            )
            wd_layout.addWidget(wd_spin); wd_layout.addWidget(wd_btn)
            self.coin_table.setCellWidget(row, 3, wd_cell)

        self.coin_total_label.setText(f"💰 Total coin value in machine: €{total/100:.2f}")

    def _add_coins(self, denom: int, count: int):
        self.sm.admin_add_coins(denom, count)
        self._refresh_all()

    def _withdraw_coins(self, denom: int, count: int):
        if self.sm.admin_withdraw_coins(denom, count):
            # Add withdrawn coins to admin wallet? (optional – here we just remove from machine)
            QMessageBox.information(self, "Withdrawn",
                                    f"Withdrew {count}× {COIN_META.get(denom, '')} from machine.")
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Error", "Not enough coins of that denomination.")

    # ─────────────────────────── Products edit tab ─────────────────────

    def _build_products_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        info = QLabel("Edit product names, prices, and icons.")
        info.setStyleSheet("color: #95a5a6; font-size: 11px;")
        layout.addWidget(info)

        self.prod_table = QTableWidget(0, 5)
        self.prod_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Price (€)", "Emoji", "Save"]
        )
        self.prod_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.prod_table.verticalHeader().setVisible(False)
        layout.addWidget(self.prod_table)

        return w

    def _populate_products_tab(self):
        products = list(self.sm.state.products.values())
        self.prod_table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.prod_table.setItem(row, 0, QTableWidgetItem(str(p.id)))

            name_edit = QLineEdit(p.name)
            self.prod_table.setCellWidget(row, 1, name_edit)

            price_edit = QDoubleSpinBox()
            price_edit.setMinimum(0.01); price_edit.setMaximum(99.99)
            price_edit.setDecimals(2); price_edit.setValue(p.price)
            self.prod_table.setCellWidget(row, 2, price_edit)

            emoji_edit = QLineEdit(p.emoji)
            emoji_edit.setMaxLength(4)
            self.prod_table.setCellWidget(row, 3, emoji_edit)

            save_btn = QPushButton("💾 Save")
            save_btn.setStyleSheet("background:#3498db;color:white;border-radius:4px;padding:4px;")
            save_btn.clicked.connect(
                lambda checked, pid=p.id, r=row: self._save_product(pid, r)
            )
            self.prod_table.setCellWidget(row, 4, save_btn)

    def _save_product(self, product_id: int, row: int):
        name  = self.prod_table.cellWidget(row, 1).text()
        price = self.prod_table.cellWidget(row, 2).value()
        emoji = self.prod_table.cellWidget(row, 3).text()
        self.sm.admin_update_product(product_id, name, price, emoji)
        self._refresh_all()
        self.products_updated.emit()
        QMessageBox.information(self, "Saved", f"Product #{product_id} updated.")

    # ─────────────────────────── Log tab ───────────────────────────────

    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)

        self.log_table = QTableWidget(0, 5)
        self.log_table.setHorizontalHeaderLabels(
            ["Time", "Type", "Product", "Paid", "Details"]
        )
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.log_table)

        refresh_btn = QPushButton("🔄 Refresh Log")
        refresh_btn.setStyleSheet("background:#2c3e50;color:white;border-radius:4px;padding:6px;")
        refresh_btn.clicked.connect(self._populate_log_tab)
        layout.addWidget(refresh_btn)

        return w

    def _populate_log_tab(self):
        rows = self.sm.get_recent_transactions()
        self.log_table.setRowCount(len(rows))
        type_icons = {
            "purchase": "🛍",
            "coin_refill": "🪙➕",
            "coin_withdraw": "🪙➖",
            "restock": "📦",
        }
        for i, (ts, type_, pid, paid, change, details) in enumerate(rows):
            self.log_table.setItem(i, 0, QTableWidgetItem(str(ts)[:16]))
            icon = type_icons.get(type_, "•")
            self.log_table.setItem(i, 1, QTableWidgetItem(f"{icon} {type_}"))
            prod_name = ""
            if pid and pid in self.sm.state.products:
                prod_name = self.sm.state.products[pid].name
            self.log_table.setItem(i, 2, QTableWidgetItem(prod_name or "—"))
            self.log_table.setItem(i, 3, QTableWidgetItem(
                f"€{paid/100:.2f}" if paid else "—"
            ))
            self.log_table.setItem(i, 4, QTableWidgetItem(details or "—"))

    # ─────────────────────────── Supabase sync tab ─────────────────────

    def _build_sync_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("☁️  Supabase Integration"))

        info = QLabel(
            "Configure your Supabase project URL and anon key to sync the\n"
            "product catalog from the cloud. Local stock levels are always\n"
            "maintained in the local database."
        )
        info.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(info)

        # URL
        url_grp = QGroupBox("Supabase URL")
        url_layout = QVBoxLayout(url_grp)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://your-project.supabase.co")
        url_layout.addWidget(self.url_input)
        layout.addWidget(url_grp)

        # Key
        key_grp = QGroupBox("Supabase Anon Key")
        key_layout = QVBoxLayout(key_grp)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("eyJ...")
        key_layout.addWidget(self.key_input)
        layout.addWidget(key_grp)

        # Load existing values
        try:
            import sqlite3
            _db_path = os.path.join(os.path.dirname(__file__), "..", "data", "vending.db")
            with sqlite3.connect(_db_path) as conn:
                url_row = conn.execute("SELECT value FROM settings WHERE key='supabase_url'").fetchone()
                key_row = conn.execute("SELECT value FROM settings WHERE key='supabase_key'").fetchone()
            if url_row: self.url_input.setText(url_row[0])
            if key_row: self.key_input.setText(key_row[0])
        except Exception:
            pass

        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Credentials")
        save_btn.setStyleSheet("background:#3498db;color:white;border-radius:6px;padding:8px;")
        save_btn.clicked.connect(self._save_supabase_creds)

        sync_btn = QPushButton("🔄 Sync Products Now")
        sync_btn.setStyleSheet("background:#8e44ad;color:white;border-radius:6px;padding:8px;")
        sync_btn.clicked.connect(self._do_sync)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(sync_btn)
        layout.addLayout(btn_row)

        self.sync_status = QLabel("")
        self.sync_status.setWordWrap(True)
        layout.addWidget(self.sync_status)

        layout.addStretch()

        # Schema hint
        schema_box = QGroupBox("Expected Supabase Table Schema (products)")
        schema_layout = QVBoxLayout(schema_box)
        schema_txt = QLabel(
            "CREATE TABLE snack_catalog (\n"
            "  id       SERIAL PRIMARY KEY,\n"
            "  name     TEXT NOT NULL,\n"
            "  recommended_price    NUMERIC(6,2) NOT NULL,\n"
            "  image_url    TEXT DEFAULT '📦',\n"
            "  quantity TEXT DEFAULT 'misc'\n"
            ");"
        )
        schema_txt.setStyleSheet("font-family: monospace; font-size: 11px; color: #2ecc71;")
        schema_layout.addWidget(schema_txt)
        layout.addWidget(schema_box)

        return w

    def _save_supabase_creds(self):
        import sqlite3, os
        db_path = os.path.join(os.path.dirname(__file__), "..", "data", "vending.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('supabase_url',?)",
                         (self.url_input.text(),))
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('supabase_key',?)",
                         (self.key_input.text(),))
        self.sync_status.setText("✅ Credentials saved.")
        self.sync_status.setStyleSheet("color: #2ecc71;")

    def _do_sync(self):
        self.sync_status.setText("⏳ Syncing…")
        ok, msg = self.sm.sync_from_supabase()
        self.sync_status.setText(("✅ " if ok else "❌ ") + msg)
        self.sync_status.setStyleSheet(f"color: {'#2ecc71' if ok else '#e74c3c'};")
        if ok:
            self._refresh_all()
            self.products_updated.emit()

    # ─────────────────────────── Refresh ───────────────────────────────

    def _refresh_all(self):
        self.sm._load_all()
        self._populate_inventory_tab()
        self._populate_coins_tab()
        self._populate_products_tab()
        self._populate_log_tab()
