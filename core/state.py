"""
state.py – Central state management for the vending machine.
All state mutations happen here; UI reads from here.
"""

import sqlite3
import os
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "vending.db")


@dataclass
class Product:
    id: int
    name: str
    price: float        # in euros
    stock: int
    emoji: str
    category: str
    enabled: bool = True

    @property
    def price_cents(self) -> int:
        return round(self.price * 100)

    @property
    def price_display(self) -> str:
        return f"€{self.price:.2f}"


@dataclass
class VendingState:
    """All runtime state for the vending machine session."""
    inserted_cents: int = 0                   # coins user put in this session
    selected_product: Optional[Product] = None
    is_admin_mode: bool = False
    products: Dict[int, Product] = field(default_factory=dict)
    coin_inventory: Dict[int, int] = field(default_factory=dict)   # denom_cents → count
    wallet: Dict[int, int] = field(default_factory=dict)           # denom_cents → count
    status_message: str = "Please choose a product"
    pending_coins: Dict[int, int] = field(default_factory=dict)    # coins inserted THIS session


class StateManager:
    """
    Manages all state transitions with persistence to SQLite.
    Acts as the single source of truth.
    """

    COIN_DENOMS = [1, 2, 5, 10, 20, 50, 100, 200]  # cents

    def __init__(self):
        self.state = VendingState()
        self._load_all()

    # ─────────────────────────── DB helpers ────────────────────────────

    def _conn(self):
        return sqlite3.connect(DB_PATH)

    def _load_all(self):
        self._load_products()
        self._load_coin_inventory()
        self._load_wallet()

    def _load_products(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id,name,price,stock,emoji,category,enabled FROM products ORDER BY name"
            ).fetchall()
        self.state.products = {
            r[0]: Product(r[0], r[1], r[2], r[3], r[4], r[5], bool(r[6]))
            for r in rows
        }

    def _load_coin_inventory(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT denomination, count FROM coin_inventory").fetchall()
        self.state.coin_inventory = {r[0]: r[1] for r in rows}

    def _load_wallet(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT denomination, count FROM wallet").fetchall()
        self.state.wallet = {r[0]: r[1] for r in rows}

    # ─────────────────────────── Auth ──────────────────────────────────

    def verify_admin_pin(self, pin: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key='admin_pin'"
            ).fetchone()
        return row and row[0] == pin

    def enter_admin_mode(self):
        self.state.is_admin_mode = True

    def exit_admin_mode(self):
        self.state.is_admin_mode = False
        self.state.status_message = "Please choose a product"

    # ─────────────────────────── Wallet ────────────────────────────────

    def wallet_total_cents(self) -> int:
        return sum(d * c for d, c in self.state.wallet.items())

    def wallet_balance_display(self) -> str:
        total = self.wallet_total_cents()
        return f"€{total / 100:.2f}"

    def wallet_add_coin(self, denom_cents: int, count: int = 1):
        """Add coins to user wallet (e.g., after receiving change)."""
        self.state.wallet[denom_cents] = self.state.wallet.get(denom_cents, 0) + count
        self._save_wallet()

    def wallet_remove_coin(self, denom_cents: int, count: int = 1) -> bool:
        """Remove coins from wallet (e.g., when inserting into machine)."""
        if self.state.wallet.get(denom_cents, 0) < count:
            return False
        self.state.wallet[denom_cents] -= count
        self._save_wallet()
        return True

    def _save_wallet(self):
        with self._conn() as conn:
            for denom, count in self.state.wallet.items():
                conn.execute(
                    "INSERT OR REPLACE INTO wallet (denomination, count) VALUES (?,?)",
                    (denom, count),
                )

    # ─────────────────────────── Coin insertion ────────────────────────

    def insert_coin(self, denom_cents: int) -> bool:
        """User inserts a coin from wallet into machine."""
        if not self.wallet_remove_coin(denom_cents):
            return False
        self.state.inserted_cents += denom_cents
        self.state.pending_coins[denom_cents] = (
            self.state.pending_coins.get(denom_cents, 0) + 1
        )
        # Add to machine inventory immediately (returned if cancelled)
        self.state.coin_inventory[denom_cents] = (
            self.state.coin_inventory.get(denom_cents, 0) + 1
        )
        self._save_coin_inventory()
        return True

    def cancel_transaction(self) -> Dict[int, int]:
        """Return all pending coins to the wallet."""
        returned = dict(self.state.pending_coins)
        for denom, count in returned.items():
            # Remove from machine
            self.state.coin_inventory[denom] = max(
                0, self.state.coin_inventory.get(denom, 0) - count
            )
            # Return to wallet
            self.state.wallet[denom] = self.state.wallet.get(denom, 0) + count
        self._save_coin_inventory()
        self._save_wallet()
        self._reset_session()
        return returned

    def _reset_session(self):
        self.state.inserted_cents = 0
        self.state.pending_coins = {}
        self.state.selected_product = None
        self.state.status_message = "Please choose a product"

    # ─────────────────────────── Purchase ──────────────────────────────

    def purchase_product(self, product_id: int) -> Tuple[bool, str, Dict[int, int]]:
        """
        Attempt to purchase product.
        Returns (success, message, change_coins_dict)
        change_coins_dict: denom → count of coins returned as change
        """
        product = self.state.products.get(product_id)
        if not product:
            return False, "Product not found.", {}
        if product.stock <= 0:
            return False, f"{product.name} is sold out!", {}
        if self.state.inserted_cents < product.price_cents:
            needed = (product.price_cents - self.state.inserted_cents) / 100
            return False, f"Insert €{needed:.2f} more.", {}

        change_cents = self.state.inserted_cents - product.price_cents
        change_coins, ok = self._calculate_change(change_cents)

        if not ok:
            return False, "Cannot make exact change. Please use correct amount or different coins.", {}

        # Deduct product stock
        product.stock -= 1
        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET stock=? WHERE id=?", (product.stock, product.id)
            )

        # Remove change coins from inventory
        for denom, count in change_coins.items():
            self.state.coin_inventory[denom] -= count
        self._save_coin_inventory()

        # Give change to user wallet
        for denom, count in change_coins.items():
            self.state.wallet[denom] = self.state.wallet.get(denom, 0) + count
        self._save_wallet()

        # Log transaction
        self._log_transaction("purchase", product_id, self.state.inserted_cents, change_cents)

        self._reset_session()
        return True, f"Enjoy your {product.name}! 🎉", change_coins

    # ─────────────────────────── Change algorithm ──────────────────────

    def _calculate_change(self, change_cents: int) -> Tuple[Dict[int, int], bool]:
        """
        Greedy change-making algorithm using available coin inventory.
        Returns (change_dict, success).
        Uses denominations from largest to smallest.
        Falls back to DP if greedy fails (for edge cases).
        """
        if change_cents == 0:
            return {}, True

        # Try greedy first
        remaining = change_cents
        result = {}
        for denom in sorted(self.state.coin_inventory.keys(), reverse=True):
            available = self.state.coin_inventory.get(denom, 0)
            if available <= 0 or denom > remaining:
                continue
            use = min(available, remaining // denom)
            if use > 0:
                result[denom] = use
                remaining -= denom * use
            if remaining == 0:
                break

        if remaining == 0:
            return result, True

        # Greedy failed – try DP (exact change)
        return self._dp_change(change_cents)

    def _dp_change(self, target: int) -> Tuple[Dict[int, int], bool]:
        """
        Dynamic programming change-making with limited coin inventory.
        Finds minimum coins or returns failure.
        """
        # Build flat list of available coins
        available = []
        for denom, count in self.state.coin_inventory.items():
            available.extend([denom] * count)

        # DP table: dp[i] = minimum coins to make i cents, or None
        INF = float("inf")
        dp = [INF] * (target + 1)
        dp[0] = 0
        coin_used: List[Optional[int]] = [None] * (target + 1)

        for coin in available:
            for amount in range(target, coin - 1, -1):
                if dp[amount - coin] + 1 < dp[amount]:
                    dp[amount] = dp[amount - coin] + 1
                    coin_used[amount] = coin

        if dp[target] == INF:
            return {}, False

        # Reconstruct
        result: Dict[int, int] = {}
        amount = target
        while amount > 0:
            coin = coin_used[amount]
            result[coin] = result.get(coin, 0) + 1
            amount -= coin

        return result, True

    # ─────────────────────────── Coin inventory (admin) ────────────────

    def admin_add_coins(self, denom_cents: int, count: int):
        self.state.coin_inventory[denom_cents] = (
            self.state.coin_inventory.get(denom_cents, 0) + count
        )
        self._save_coin_inventory()
        self._log_transaction("coin_refill", None, denom_cents * count, 0,
                              f"Added {count}x {denom_cents}ct coins")

    def admin_withdraw_coins(self, denom_cents: int, count: int) -> bool:
        current = self.state.coin_inventory.get(denom_cents, 0)
        if current < count:
            return False
        self.state.coin_inventory[denom_cents] = current - count
        self._save_coin_inventory()
        self._log_transaction("coin_withdraw", None, denom_cents * count, 0,
                              f"Withdrew {count}x {denom_cents}ct coins")
        return True

    def _save_coin_inventory(self):
        with self._conn() as conn:
            for denom, count in self.state.coin_inventory.items():
                conn.execute(
                    "INSERT OR REPLACE INTO coin_inventory (denomination, count) VALUES (?,?)",
                    (denom, count),
                )

    # ─────────────────────────── Product (admin) ───────────────────────

    def admin_refill_product(self, product_id: int, qty: int):
        product = self.state.products.get(product_id)
        if not product:
            return
        product.stock += qty
        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET stock=? WHERE id=?", (product.stock, product_id)
            )
        self._log_transaction("restock", product_id, 0, 0, f"Restocked +{qty}")

    def admin_update_product(self, product_id: int, name: str, price: float, emoji: str):
        product = self.state.products.get(product_id)
        if not product:
            return
        product.name = name
        product.price = price
        product.emoji = emoji
        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET name=?, price=?, emoji=? WHERE id=?",
                (name, price, emoji, product_id),
            )

    # ─────────────────────────── Low-stock check ───────────────────────

    def get_low_stock_products(self) -> List[Product]:
        """Return products at or below the low-stock threshold."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key='low_stock_threshold'"
            ).fetchone()
        threshold = int(row[0]) if row else 3
        return [p for p in self.state.products.values() if p.stock <= threshold]

    def get_inventory_summary(self) -> Dict:
        low = self.get_low_stock_products()
        out_of_stock = [p for p in self.state.products.values() if p.stock == 0]
        total_coins = sum(
            d * c for d, c in self.state.coin_inventory.items()
        )
        return {
            "low_stock": low,
            "out_of_stock": out_of_stock,
            "total_coin_value": total_coins,
            "needs_attention": len(low) > 0 or len(out_of_stock) > 0,
        }

    # ─────────────────────────── Transactions ──────────────────────────

    def _log_transaction(self, type_: str, product_id, amount_paid, change_given, details=""):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO transactions (type,product_id,amount_paid,change_given,details) VALUES (?,?,?,?,?)",
                (type_, product_id, amount_paid, change_given, details),
            )

    def get_recent_transactions(self, limit=20) -> List:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT ts, type, product_id, amount_paid, change_given, details
                   FROM transactions ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return rows

    # ─────────────────────────── Supabase sync ─────────────────────────

    def sync_from_supabase(self) -> Tuple[bool, str]:
        """Pull product catalog from Supabase and merge with local."""
        try:
            from supabase import create_client
            with self._conn() as conn:
                url = conn.execute(
                    "SELECT value FROM settings WHERE key='supabase_url'"
                ).fetchone()[0]
                key = conn.execute(
                    "SELECT value FROM settings WHERE key='supabase_key'"
                ).fetchone()[0]

            if "YOUR_SUPABASE" in url:
                return False, "Supabase credentials not configured."

            sb = create_client(url, key)
            resp = sb.table("snack_catalog").select("*").execute()
            products = resp.data

            skipped = 0
            synced = 0
            skip_reasons = []

            # Debug: log the raw keys from the first row so mismatches are visible
            if products:
                import logging
                logging.warning(f"[Supabase] First row keys: {list(products[0].keys())}")
                logging.warning(f"[Supabase] First row data: {products[0]}")

            with self._conn() as conn:
                for p in products:
                    try:
                        # id is a UUID string – store as text, use a hash for
                        # the integer primary key expected by the local schema
                        uuid_str = str(p["id"])
                        # Deterministic integer from UUID (lower 8 hex digits)
                        prod_id  = int(uuid_str.replace("-", "")[-8:], 16) & 0x7FFFFFFF
                        name     = str(p.get("name") or "Unknown")

                        # recommended_price is stored in CENTS (e.g. 150 = €1.50)
                        raw_price = p.get("recommended_price")
                        if raw_price is None:
                            price = 0.00
                        else:
                            if isinstance(raw_price, str):
                                raw_price = raw_price.strip().replace(",", ".")
                            price = round(float(raw_price) / 100, 2)  # cents -> euros

                        image_url = str(p.get("image_url") or "📦")
                        quantity  = int(p.get("quantity") or 0)

                    except (KeyError, TypeError, ValueError) as e:
                        skip_reasons.append(f"row id={p.get('id','?')}: {e}")
                        skipped += 1
                        continue

                    # Check if product already exists locally
                    existing = conn.execute(
                        "SELECT stock FROM products WHERE id=?", (prod_id,)
                    ).fetchone()

                    if existing:
                        # Update catalog fields only – never touch local stock
                        conn.execute(
                            """UPDATE products
                               SET name=?, price=?, emoji=?
                               WHERE id=?""",
                            (name, raw_price, image_url, prod_id),
                        )
                    else:
                        # New product – use Supabase quantity as opening stock
                        conn.execute(
                            """INSERT INTO products
                               (id, name, price, stock, emoji, category)
                               VALUES (?,?,?,?,?,?)""",
                            (prod_id, name, raw_price, quantity, image_url, "misc"),
                        )
                    synced += 1

            # Remove original seeded placeholder products (id 1-9)
            # now that we have real products from Supabase
            if synced > 0:
                synced_ids = set()
                with self._conn() as conn:
                    rows = conn.execute("SELECT id FROM products").fetchall()
                    for (rid,) in rows:
                        synced_ids.add(rid)
                # IDs 1-9 are the local seeds; any hashed UUID-derived ID is >> 9
                seed_ids = [i for i in synced_ids if 1 <= i <= 9]
                if seed_ids and any(i > 9 for i in synced_ids):
                    with self._conn() as conn:
                        conn.execute(
                            f"DELETE FROM products WHERE id IN ({','.join('?'*len(seed_ids))})",
                            seed_ids,
                        )

            self._load_products()
            msg = f"Synced {synced} products from Supabase."
            if skipped:
                reasons = "; ".join(skip_reasons[:3])
                if len(skip_reasons) > 3:
                    reasons += f" ...+{len(skip_reasons)-3} more"
                msg += f"\n\n{skipped} rows skipped. Reasons:\n{reasons}"
            return True, msg
        except ImportError:
            return False, "supabase-py not installed. Run: pip install supabase"
        except Exception as e:
            return False, f"Sync failed: {e}"
