import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  active_ingredient TEXT NOT NULL DEFAULT '',
  form TEXT NOT NULL DEFAULT '',
  dosage_pl TEXT NOT NULL DEFAULT '',
  dosage_ru TEXT NOT NULL DEFAULT '',
  dosage_uk TEXT NOT NULL DEFAULT '',
  dosage_en TEXT NOT NULL DEFAULT '',
  description_pl TEXT NOT NULL DEFAULT '',
  description_ru TEXT NOT NULL DEFAULT '',
  description_uk TEXT NOT NULL DEFAULT '',
  description_en TEXT NOT NULL DEFAULT '',
  expiry_date TEXT,
  opened_at TEXT,
  discard_after_days INTEGER,
  quantity REAL NOT NULL DEFAULT 0,
  unit TEXT NOT NULL DEFAULT 'pieces',
  low_stock_threshold REAL NOT NULL DEFAULT 3,
  photo_path TEXT,
  ai_status TEXT NOT NULL DEFAULT 'needs_ai_data',
  low_stock_notified INTEGER NOT NULL DEFAULT 0,
  snooze_expiry_until TEXT,
  snooze_opened_until TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  medicine_id INTEGER NOT NULL REFERENCES medicines(id),
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  actor TEXT NOT NULL DEFAULT '',
  delta REAL NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS allowed_users (
  telegram_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL DEFAULT 'member',
  lang TEXT NOT NULL DEFAULT 'pl'
);
CREATE TABLE IF NOT EXISTS shopping_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  added_by TEXT NOT NULL DEFAULT '',
  added_at TEXT NOT NULL DEFAULT (datetime('now')),
  bought INTEGER NOT NULL DEFAULT 0,
  bought_by TEXT,
  bought_at TEXT,
  from_medicine_id INTEGER
);
"""

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn

def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
