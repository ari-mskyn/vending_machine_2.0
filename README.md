# 🏪 Euro Vending Machine

A full-featured vending machine simulator built with **PyQt6** + **SQLite** (with optional Supabase cloud sync).

---

## 📁 Project Structure

```
vending_machine/
├── main.py                  ← Entry point
├── requirements.txt
├── data/
│   ├── db_init.py           ← DB schema + seed data
│   └── vending.db           ← Auto-created SQLite database
├── core/
│   └── state.py             ← State management + business logic
└── ui/
    ├── main_window.py       ← Main vending machine UI
    ├── coin_dialog.py       ← Coin insertion dialog
    ├── admin_panel.py       ← Admin panel (PIN-protected)
    └── styles.py            ← QSS stylesheets
```

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install PyQt6 supabase
```

### 2. Initialize the database

```bash
cd vending_machine
python data/db_init.py
```

### 3. Run the app

```bash
python main.py
```

---

## 🎮 How to Use

### Customer Mode

| Action | How |
|---|---|
| Select a product | Click any product in the 3×3 grid |
| Insert coins | Click **🪙 INSERT COIN** → click coins from your wallet |
| Buy | Click **✅ BUY** (enabled when enough money inserted) |
| Cancel / get coins back | Click **↩ CANCEL / RETURN** |

The **display screen** (right panel) shows:
- Status message
- Inserted amount so far
- Selected product + price

The **wallet** starts pre-loaded with some coins and persists between sessions.

---

### Admin Mode

Click **🔧 ADMIN** and enter the PIN: **`1234`**

| Tab | What you can do |
|---|---|
| 📦 Inventory | See stock levels, refill products. ⚠ alerts for low stock, ❌ for out-of-stock |
| 🪙 Coins | See coin inventory, add coin rolls, withdraw cash |
| ✏️ Products | Edit product names, prices, emojis |
| 📋 Log | View recent transactions |
| ☁️ Supabase Sync | Enter credentials and pull product catalog from cloud |

---

## 🪙 Euro Coins Supported

| Coin | Value |
|---|---|
| 1 ct | €0.01 |
| 2 ct | €0.02 |
| 5 ct | €0.05 |
| 10 ct | €0.10 |
| 20 ct | €0.20 |
| 50 ct | €0.50 |
| €1 | €1.00 |
| €2 | €2.00 |

---

## 🔄 Change Algorithm

The machine uses a **two-phase change algorithm**:

1. **Greedy phase** – Gives change from largest coins to smallest. Fast and works for most cases.
2. **DP fallback** – If greedy cannot make exact change (due to limited inventory), a dynamic programming knapsack algorithm finds the optimal combination, or reports that exact change cannot be made.

---

## ☁️ Supabase Integration

To connect to Supabase:

1. Create a project at [supabase.com](https://supabase.com)
2. Create a `products` table:

```sql
CREATE TABLE products (
  id       SERIAL PRIMARY KEY,
  name     TEXT NOT NULL,
  price    NUMERIC(6,2) NOT NULL,
  emoji    TEXT DEFAULT '📦',
  category TEXT DEFAULT 'misc'
);
```

3. Open Admin Panel → **☁️ Supabase Sync** tab
4. Enter your Project URL and anon key → **Save** → **Sync**

Stock levels are always managed locally; Supabase only provides the product catalog.

---

## ⚙️ Configuration

Edit `data/db_init.py` to change:
- `ADMIN_PIN` – Default: `1234`
- `INITIAL_COINS` – Starting coin inventory
- `PRODUCTS` – Product catalog

All settings are stored in the `settings` table in the SQLite database.

---

## 🧪 Low Stock Alert

The machine flags products as **low stock** when `stock ≤ 3` (configurable in the `settings` table as `low_stock_threshold`). The Admin Panel shows a red banner listing all products that need attention.
