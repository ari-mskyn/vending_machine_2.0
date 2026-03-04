"""
db_init.py – Creates and seeds the local SQLite mock database.
Run this once before starting the app: python db_init.py
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "vending.db")


PRODUCTS = [
    {"id": 1, "name": "Cola",         "price": 1.50, "stock": 10, "emoji": "🥤", "category": "drink"},
    {"id": 2, "name": "Water",         "price": 0.80, "stock": 10, "emoji": "💧", "category": "drink"},
    {"id": 3, "name": "Orange Juice",  "price": 1.80, "stock": 8,  "emoji": "🍊", "category": "drink"},
    {"id": 4, "name": "Chips",         "price": 1.20, "stock": 10, "emoji": "🥔", "category": "snack"},
    {"id": 5, "name": "Chocolate",     "price": 1.00, "stock": 10, "emoji": "🍫", "category": "snack"},
    {"id": 6, "name": "Gummy Bears",   "price": 0.90, "stock": 5,  "emoji": "🐻", "category": "snack"},
    {"id": 7, "name": "Energy Drink",  "price": 2.20, "stock": 8,  "emoji": "⚡", "category": "drink"},
    {"id": 8, "name": "Pretzel",       "price": 0.70, "stock": 3,  "emoji": "🥨", "category": "snack"},
    {"id": 9, "name": "Sandwich",      "price": 3.50, "stock": 4,  "emoji": "🥪", "category": "food"},
]

# Euro coin denominations in cents (to avoid float arithmetic)
COIN_DENOMINATIONS = [1, 2, 5, 10, 20, 50, 100, 200]  # cents
COIN_LABELS = {
    1:   "1 ct",
    2:   "2 ct",
    5:   "5 ct",
    10:  "10 ct",
    20:  "20 ct",
    50:  "50 ct",
    100: "€1.00",
    200: "€2.00",
}

# Initial coin inventory in the machine (count per denomination)
INITIAL_COINS = {
    1:   20,
    2:   20,
    5:   20,
    10:  20,
    20:  20,
    50:  10,
    100: 10,
    200: 5,
}

# Admin credentials (hashed would be better in production)
ADMIN_PIN = "1234"


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Products table ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id       INTEGER PRIMARY KEY,
            name     TEXT    NOT NULL,
            price    REAL    NOT NULL,
            stock    INTEGER NOT NULL DEFAULT 0,
            emoji    TEXT    NOT NULL DEFAULT '📦',
            category TEXT    NOT NULL DEFAULT 'misc',
            enabled  INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Coin inventory table ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS coin_inventory (
            denomination INTEGER PRIMARY KEY,
            count        INTEGER NOT NULL DEFAULT 0
        )
    """)

    # ── Wallet table ─────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS wallet (
            denomination INTEGER PRIMARY KEY,
            count        INTEGER NOT NULL DEFAULT 0
        )
    """)

    # ── Transaction log ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL DEFAULT (datetime('now')),
            type        TEXT    NOT NULL,
            product_id  INTEGER,
            amount_paid INTEGER,
            change_given INTEGER,
            details     TEXT
        )
    """)

    # ── Settings table ───────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Seed products (only if empty)
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO products (id,name,price,stock,emoji,category) VALUES (?,?,?,?,?,?)",
            [(p["id"], p["name"], p["price"], p["stock"], p["emoji"], p["category"]) for p in PRODUCTS],
        )

    # Seed coin inventory
    c.execute("SELECT COUNT(*) FROM coin_inventory")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO coin_inventory (denomination, count) VALUES (?,?)",
            list(INITIAL_COINS.items()),
        )

    # Seed wallet (start with some coins)
    c.execute("SELECT COUNT(*) FROM wallet")
    if c.fetchone()[0] == 0:
        wallet_seed = {1: 5, 2: 5, 5: 3, 10: 3, 20: 2, 50: 2, 100: 2, 200: 1}
        c.executemany(
            "INSERT INTO wallet (denomination, count) VALUES (?,?)",
            list(wallet_seed.items()),
        )

    # Settings
    c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('admin_pin', ?)", (ADMIN_PIN,))
    c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('low_stock_threshold', '3')")
    c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('supabase_url', 'YOUR_SUPABASE_URL_HERE')")
    c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('supabase_key', 'YOUR_SUPABASE_ANON_KEY_HERE')")

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
