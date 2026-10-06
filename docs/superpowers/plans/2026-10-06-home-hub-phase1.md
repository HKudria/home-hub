# Home Hub Phase 1 — Medicine Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A self-hosted medicine tracker: mobile web app with camera capture + AI extraction (z.ai), expiry/opened/low-stock Telegram notifications, conversational Telegram dose tracking, UI in PL/RU/UK/EN — one Docker container.

**Architecture:** Python FastAPI app with SQLite, aiogram long-polling bot, APScheduler daily job, httpx calls to z.ai's OpenAI-compatible API. All state in one Docker volume (SQLite file + photos + backups).

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLite (stdlib `sqlite3`), aiogram 3, APScheduler, httpx, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-06-home-hub-design.md`

## Global Constraints

- Python 3.12; all dependencies pinned in `requirements.txt`.
- SQLite only — no other database.
- Telegram via **long polling** only (no inbound ports, no webhooks).
- Web app has no mandatory login (VPN-only per spec); optional password behind `WEB_PASSWORD` env, off by default.
- UI languages exactly: `pl, ru, uk, en` (en is fallback). Medicine descriptions stored in all four.
- Notification schedule (from spec): expiry → 7 days before and on expiry day, then every 30 days after; opened-after → 1 day before and on discard day; low stock → when quantity ≤ threshold and again when taking the last dose.
- Bot never guesses ambiguous medicines — always replies with inline buttons.
- Photos never block saving: AI failure → `ai_status='needs_ai_data'`, background retry.
- All timestamps stored as ISO-8601 date strings (`YYYY-MM-DD`) in SQLite; dates evaluated in local server time.
- Tests run with `python -m pytest -v` from the repo root; every task's tests must pass before commit.

---

### Task 1: Project scaffold and configuration

**Files:**
- Create: `requirements.txt`, `.env.example`, `app/__init__.py`, `app/config.py`
- Test: `tests/test_config.py`, `tests/conftest.py`

**Interfaces:**
- Produces: `app.config.Settings` dataclass; `load_settings() -> Settings` reading env vars: `ZAI_API_KEY`, `ZAI_BASE_URL` (default `https://api.z.ai/api/paas/v4`), `ZAI_VISION_MODEL` (default `glm-4.5v`), `ZAI_TEXT_MODEL` (default `glm-4.6`), `TELEGRAM_BOT_TOKEN`, `ADMIN_TELEGRAM_ID` (int), `DAILY_CHECK_HOUR` (int, default 9), `WEB_PASSWORD` (default empty), `DATA_DIR` (default `./data`), `BACKUP_KEEP_DAYS` (default 14).

- [ ] **Step 1: Create directory structure and files**

```bash
mkdir -p app/ai app/services app/bot app/web/templates app/web/static tests
touch app/__init__.py app/ai/__init__.py app/services/__init__.py app/bot/__init__.py app/web/__init__.py tests/__init__.py
```

`requirements.txt`:

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
jinja2==3.1.5
aiogram==3.15.0
apscheduler==3.11.0
httpx==0.28.1
python-multipart==0.0.20
pytest==8.3.4
pytest-asyncio==0.25.0
```

`.env.example`:

```
ZAI_API_KEY=your-zai-key
ZAI_BASE_URL=https://api.z.ai/api/paas/v4
ZAI_VISION_MODEL=glm-4.5v
ZAI_TEXT_MODEL=glm-4.6
TELEGRAM_BOT_TOKEN=your-bot-token
ADMIN_TELEGRAM_ID=123456789
DAILY_CHECK_HOUR=9
WEB_PASSWORD=
DATA_DIR=./data
BACKUP_KEEP_DAYS=14
```

- [ ] **Step 2: Write failing test**

`tests/test_config.py`:

```python
import os
from app.config import load_settings

def test_load_settings_defaults(monkeypatch):
    for k in ["ZAI_API_KEY", "TELEGRAM_BOT_TOKEN", "ADMIN_TELEGRAM_ID"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ZAI_API_KEY", "k1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t1")
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "42")
    s = load_settings()
    assert s.zai_api_key == "k1"
    assert s.admin_telegram_id == 42
    assert s.daily_check_hour == 9
    assert s.data_dir == "./data"
    assert s.backup_keep_days == 14
    assert s.web_password == ""
```

`tests/conftest.py`:

```python
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: app.config`)

- [ ] **Step 4: Implement `app/config.py`**

```python
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    zai_api_key: str
    zai_base_url: str
    zai_vision_model: str
    zai_text_model: str
    telegram_bot_token: str
    admin_telegram_id: int
    daily_check_hour: int
    web_password: str
    data_dir: str
    backup_keep_days: int

def load_settings() -> Settings:
    return Settings(
        zai_api_key=os.environ.get("ZAI_API_KEY", ""),
        zai_base_url=os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4"),
        zai_vision_model=os.environ.get("ZAI_VISION_MODEL", "glm-4.5v"),
        zai_text_model=os.environ.get("ZAI_TEXT_MODEL", "glm-4.6"),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        admin_telegram_id=int(os.environ.get("ADMIN_TELEGRAM_ID", "0")),
        daily_check_hour=int(os.environ.get("DAILY_CHECK_HOUR", "9")),
        web_password=os.environ.get("WEB_PASSWORD", ""),
        data_dir=os.environ.get("DATA_DIR", "./data"),
        backup_keep_days=int(os.environ.get("BACKUP_KEEP_DAYS", "14")),
    )
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: project scaffold and settings"
```

---

### Task 2: Database layer and schema

**Files:**
- Create: `app/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `init_db(db_path: str) -> sqlite3.Connection` (creates schema, enables WAL + foreign keys, returns open connection); `get_conn(db_path: str) -> sqlite3.Connection` (opens existing). Tables: `medicines`, `events`, `allowed_users` (full DDL below). Row factory is `sqlite3.Row` on all connections.

- [ ] **Step 1: Write failing test**

`tests/test_db.py`:

```python
from app.db import init_db

def test_init_db_creates_tables(tmp_path):
    conn = init_db(str(tmp_path / "hub.db"))
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"medicines", "events", "allowed_users"} <= names

def test_medicines_defaults(tmp_path):
    conn = init_db(str(tmp_path / "hub.db"))
    conn.execute(
        "INSERT INTO medicines (name) VALUES (?)", ("Test",))
    row = conn.execute("SELECT * FROM medicines").fetchone()
    assert row["quantity"] == 0
    assert row["low_stock_threshold"] == 3
    assert row["ai_status"] == "needs_ai_data"
    assert row["unit"] == "pieces"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: app.db`)

- [ ] **Step 3: Implement `app/db.py`**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/test_db.py && git commit -m "feat: sqlite schema and connection helpers"
```

---

### Task 3: Medicine service (CRUD, doses, opened, events)

**Files:**
- Create: `app/services/medicine_service.py`
- Test: `tests/test_medicine_service.py`

**Interfaces:**
- Consumes: `app.db.init_db`.
- Produces: class `MedicineService(conn)` with:
  - `add(fields: dict) -> int` (dict keys = medicine columns except id/timestamps; sets `ai_status='ok'` unless caller overrides)
  - `get(medicine_id: int) -> sqlite3.Row | None`
  - `list_all() -> list[sqlite3.Row]` (ordered by expiry date, nulls last)
  - `update(medicine_id: int, fields: dict)` (also bumps `updated_at`)
  - `take_dose(medicine_id: int, amount: float, actor: str) -> sqlite3.Row | None` (decrements, floors at 0, appends event, resets `low_stock_notified` to 0 if quantity went **up**, returns updated row or None if missing)
  - `mark_opened(medicine_id: int, day: str, actor: str)` (sets `opened_at=day`, appends event)
  - `discard(medicine_id: int, actor: str)` (quantity→0, appends event note 'discarded')
  - `recent_events(limit: int = 20) -> list[sqlite3.Row]`

- [ ] **Step 1: Write failing tests**

`tests/test_medicine_service.py`:

```python
import datetime
from app.db import init_db
from app.services.medicine_service import MedicineService

def make_svc(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    return MedicineService(conn), conn

def test_add_and_get(tmp_path):
    svc, _ = make_svc(tmp_path)
    mid = svc.add({"name": "Paracetamol 500", "quantity": 20, "expiry_date": "2027-01-01"})
    row = svc.get(mid)
    assert row["name"] == "Paracetamol 500"
    assert row["ai_status"] == "ok"

def test_list_all_nulls_last(tmp_path):
    svc, _ = make_svc(tmp_path)
    svc.add({"name": "NoDate"})
    svc.add({"name": "Dated", "expiry_date": "2027-05-01"})
    rows = svc.list_all()
    assert rows[0]["name"] == "Dated"

def test_take_dose(tmp_path):
    svc, conn = make_svc(tmp_path)
    mid = svc.add({"name": "A", "quantity": 5, "low_stock_threshold": 3})
    row = svc.take_dose(mid, 1, "herman")
    assert row["quantity"] == 4
    ev = conn.execute("SELECT * FROM events WHERE medicine_id=?", (mid,)).fetchone()
    assert ev["delta"] == -1 and ev["actor"] == "herman"

def test_take_dose_floors_at_zero(tmp_path):
    svc, _ = make_svc(tmp_path)
    mid = svc.add({"name": "A", "quantity": 1})
    row = svc.take_dose(mid, 5, "x")
    assert row["quantity"] == 0

def test_take_dose_resets_low_stock_flag_when_restocked(tmp_path):
    svc, conn = make_svc(tmp_path)
    mid = svc.add({"name": "A", "quantity": 2})
    svc.take_dose(mid, 1, "x")  # low stock triggered elsewhere
    conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?", (mid,))
    conn.commit()
    svc.take_dose(mid, -10, "restock")  # delta negative amount => adds
    row = svc.get(mid)
    assert row["low_stock_notified"] == 0

def test_mark_opened_and_discard(tmp_path):
    svc, conn = make_svc(tmp_path)
    mid = svc.add({"name": "Syrup", "discard_after_days": 30})
    svc.mark_opened(mid, "2026-10-06", "herman")
    assert svc.get(mid)["opened_at"] == "2026-10-06"
    svc.discard(mid, "herman")
    assert svc.get(mid)["quantity"] == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_medicine_service.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `app/services/medicine_service.py`**

```python
import sqlite3

COLUMNS = [
    "name", "active_ingredient", "form",
    "dosage_pl", "dosage_ru", "dosage_uk", "dosage_en",
    "description_pl", "description_ru", "description_uk", "description_en",
    "expiry_date", "opened_at", "discard_after_days", "quantity", "unit",
    "low_stock_threshold", "photo_path", "ai_status",
]

class MedicineService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, fields: dict) -> int:
        fields = {k: v for k, v in fields.items() if k in COLUMNS}
        fields.setdefault("ai_status", "ok")
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO medicines ({cols}) VALUES ({marks})", list(fields.values()))
        self.conn.commit()
        return cur.lastrowid

    def get(self, medicine_id: int):
        return self.conn.execute(
            "SELECT * FROM medicines WHERE id=?", (medicine_id,)).fetchone()

    def list_all(self):
        return self.conn.execute(
            "SELECT * FROM medicines ORDER BY (expiry_date IS NULL), expiry_date").fetchall()

    def update(self, medicine_id: int, fields: dict):
        fields = {k: v for k, v in fields.items() if k in COLUMNS}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(
            f"UPDATE medicines SET {sets}, updated_at=datetime('now') WHERE id=?",
            [*fields.values(), medicine_id])
        self.conn.commit()

    def _event(self, medicine_id: int, actor: str, delta: float, note: str = ""):
        self.conn.execute(
            "INSERT INTO events (medicine_id, actor, delta, note) VALUES (?,?,?,?)",
            (medicine_id, actor, delta, note))

    def take_dose(self, medicine_id: int, amount: float, actor: str):
        row = self.get(medicine_id)
        if row is None:
            return None
        new_q = max(0.0, row["quantity"] - amount)
        reset = new_q > row["quantity"]
        self.conn.execute(
            "UPDATE medicines SET quantity=?, low_stock_notified=?, updated_at=datetime('now') WHERE id=?",
            (new_q, 0 if reset else row["low_stock_notified"], medicine_id))
        self._event(medicine_id, actor, -amount)
        self.conn.commit()
        return self.get(medicine_id)

    def mark_opened(self, medicine_id: int, day: str, actor: str):
        self.update(medicine_id, {"opened_at": day})
        self._event(medicine_id, actor, 0, "opened")
        self.conn.commit()

    def discard(self, medicine_id: int, actor: str):
        self.update(medicine_id, {"quantity": 0})
        self._event(medicine_id, actor, 0, "discarded")
        self.conn.commit()

    def recent_events(self, limit: int = 20):
        return self.conn.execute(
            "SELECT e.*, m.name FROM events e JOIN medicines m ON m.id=e.medicine_id "
            "ORDER BY e.id DESC LIMIT ?", (limit,)).fetchall()
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_medicine_service.py -v`
Expected: PASS (all 6)

- [ ] **Step 5: Commit**

```bash
git add app/services/medicine_service.py tests/test_medicine_service.py && git commit -m "feat: medicine service with doses, opened tracking, events"
```

---

### Task 4: Alert evaluation

**Files:**
- Create: `app/services/alerts.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Consumes: `MedicineService.list_all()`.
- Produces: `@dataclass Alert: kind: str, medicine_id: int, name: str, days: int` where `kind ∈ {"expiry_soon", "expiry_today", "expired", "opened_soon", "opened_today", "low_stock", "low_stock_last"}` and `evaluate(conn, today: str) -> list[Alert]` (pure function of data + date; snoozes honored via `snooze_expiry_until` / `snooze_opened_until`; `low_stock` fires only when `low_stock_notified=0`; `low_stock_last` fires when quantity becomes 0 via a dose, detected by quantity == 0 and `quantity > 0` no longer relevant — use quantity == 0 and threshold > 0 and `low_stock_notified=0`).

- [ ] **Step 1: Write failing tests**

`tests/test_alerts.py`:

```python
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.alerts import evaluate

def setup_med(tmp_path, **fields):
    conn = init_db(str(tmp_path / "t.db"))
    svc = MedicineService(conn)
    mid = svc.add({"name": "M", **fields})
    return conn, svc, mid

def test_expiry_7_days(tmp_path):
    conn, svc, mid = setup_med(tmp_path, expiry_date="2026-10-13")
    alerts = evaluate(conn, "2026-10-06")
    assert [a.kind for a in alerts] == ["expiry_soon"] and alerts[0].days == 7

def test_expiry_day(tmp_path):
    conn, svc, mid = setup_med(tmp_path, expiry_date="2026-10-06")
    assert [a.kind for a in evaluate(conn, "2026-10-06")] == ["expiry_today"]

def test_expired_monthly(tmp_path):
    conn, svc, mid = setup_med(tmp_path, expiry_date="2026-09-06")
    assert [a.kind for a in evaluate(conn, "2026-10-06")] == ["expired"]
    assert evaluate(conn, "2026-10-07") == []  # not on a 30-day boundary

def test_expiry_snooze(tmp_path):
    conn, svc, mid = setup_med(tmp_path, expiry_date="2026-10-06",
                               snooze_expiry_until="2026-11-06")
    assert evaluate(conn, "2026-10-06") == []
    assert [a.kind for a in evaluate(conn, "2026-11-06")] == ["expiry_today"]

def test_opened_one_day_before_and_day(tmp_path):
    conn, svc, mid = setup_med(tmp_path, opened_at="2026-09-06", discard_after_days=30)
    assert [a.kind for a in evaluate(conn, "2026-10-05")] == ["opened_soon"]
    assert [a.kind for a in evaluate(conn, "2026-10-06")] == ["opened_today"]

def test_low_stock_once_until_restock(tmp_path):
    conn, svc, mid = setup_med(tmp_path, quantity=3, low_stock_threshold=3)
    assert [a.kind for a in evaluate(conn, "2026-10-06")] == ["low_stock"]
    conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?", (mid,)); conn.commit()
    assert evaluate(conn, "2026-10-06") == []

def test_last_dose(tmp_path):
    conn, svc, mid = setup_med(tmp_path, quantity=0, low_stock_threshold=3)
    assert [a.kind for a in evaluate(conn, "2026-10-06")] == ["low_stock_last"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_alerts.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `app/services/alerts.py`**

```python
import datetime
from dataclasses import dataclass

@dataclass
class Alert:
    kind: str
    medicine_id: int
    name: str
    days: int

def _d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)

def evaluate(conn, today: str) -> list[Alert]:
    t = _d(today)
    out = []
    for m in conn.execute("SELECT * FROM medicines").fetchall():
        if m["expiry_date"] and not (m["snooze_expiry_until"] and t <= _d(m["snooze_expiry_until"])):
            d = (_d(m["expiry_date"]) - t).days
            if d == 7:
                out.append(Alert("expiry_soon", m["id"], m["name"], d))
            elif d == 0:
                out.append(Alert("expiry_today", m["id"], m["name"], d))
            elif d < 0 and (-d) % 30 == 0:
                out.append(Alert("expired", m["id"], m["name"], d))
        if m["opened_at"] and m["discard_after_days"] and not (
                m["snooze_opened_until"] and t <= _d(m["snooze_opened_until"])):
            discard = _d(m["opened_at"]) + datetime.timedelta(days=m["discard_after_days"])
            d = (discard - t).days
            if d == 1:
                out.append(Alert("opened_soon", m["id"], m["name"], d))
            elif d == 0:
                out.append(Alert("opened_today", m["id"], m["name"], d))
        if m["quantity"] <= m["low_stock_threshold"] and not m["low_stock_notified"]:
            kind = "low_stock_last" if m["quantity"] == 0 else "low_stock"
            out.append(Alert(kind, m["id"], m["name"], int(m["quantity"])))
    return out
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_alerts.py -v`
Expected: PASS (all 7)

- [ ] **Step 5: Commit**

```bash
git add app/services/alerts.py tests/test_alerts.py && git commit -m "feat: alert evaluation (expiry, opened-after, low stock, snoozes)"
```

---

### Task 5: i18n catalog

**Files:**
- Create: `app/i18n.py`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces: `LANGS = ("en", "pl", "ru", "uk")`; `DEFAULT_LANG = "pl"` (bot language default per spec); `t(lang: str, key: str, **kwargs) -> str` — falls back to `en`, then to the key itself; `detect_lang(text: str) -> str` (cyrillic heuristic: Ukrainian letters і/ї/є/→ `uk`, else `ru`, else `en`; Polish diacritics ąćęłńóśźż → `pl`).

Keys needed (write all four translations for each): `app_name`, `add_medicine`, `expires_in_days`, `expired_days_ago`, `expires_today`, `discard_soon`, `discard_today`, `low_stock`, `last_dose`, `quantity_left`, `took`, `opened_on`, `no_match`, `which_one`, `symptom_none`, `symptom_found`, `expiring_soon_list`, `approved`, `ask_admin`, `discarded`, `snoozed`, `added_to_list`, `list_title`, `no_expiry`, `take_dose`, `mark_opened`, `re-read_photo`, `save`, `edit`, `language`, `search_placeholder`.

- [ ] **Step 1: Write failing test**

```python
from app.i18n import t, detect_lang, LANGS

def test_langs():
    assert LANGS == ("en", "pl", "ru", "uk")

def test_fallback_to_en():
    assert t("xx", "app_name") == t("en", "app_name")

def test_formatting():
    assert t("en", "expires_in_days", name="A", days=7) == "A expires in 7 days"

def test_detect():
    assert detect_lang("wziąłem paracetamol") == "pl"
    assert detect_lang("я взяв парацетамол") in ("ru", "uk")
    assert detect_lang("я приняв") == "ru"
    assert detect_lang("узяв") == "uk"
    assert detect_lang("took a pill") == "en"
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_i18n.py -v` → FAIL

- [ ] **Step 3: Implement `app/i18n.py`** — a `MESSAGES: dict[str, dict[str, str]]` with all keys × 4 languages (English formats: `app_name="Home Hub"`, `expires_in_days="{name} expires in {days} days"`, `expired_days_ago="{name} expired {days} days ago"`, `expires_today="{name} expires TODAY"`, `discard_soon="{name} must be discarded tomorrow (opened {opened})"`, `discard_today="{name} must be discarded today (opened {opened})"`, `low_stock="{name}: only {qty} left"`, `last_dose="{name}: that was the last dose"`, `took="OK — {name}: {qty} {unit} left"`, `opened_on="{name} marked opened on {opened}"`, `no_match="I couldn't find that medicine."`, `which_one="Which one?"`, `symptom_none="Nothing in your cabinet matches."`, `symptom_found="For that you have:"`, `expiring_soon_list="Expiring within 7 days:"`, `approved="You're approved! ✅"`, `ask_admin="Hi! I asked the admin to approve you."`, `discarded="Marked as discarded 🗑"`, `snoozed="Snoozed ⏰"`, `added_to_list="Added to the shopping list 🛒"`, `list_title="Medicine cabinet"`, `no_expiry="No expiry date set"`, `take_dose="Took a dose"`, `mark_opened="Mark opened"`, `reread_photo="Re-read photo"`, `save="Save"`, `edit="Edit"`, `language="Language"`, `search_placeholder="Search..."`). Polish, Russian, Ukrainian translations written by the implementer (natural, short UI strings).

`detect_lang`:

```python
def detect_lang(text: str) -> str:
    low = text.lower()
    if any(c in low for c in "іїєґ"):
        return "uk"
    if any("Ѐ" <= c <= "ӿ" for c in low):
        return "ru"
    if any(c in low for c in "ąćęłńóśźż"):
        return "pl"
    return "en"
```

- [ ] **Step 4: Run tests** — Expected: PASS
- [ ] **Step 5: Commit** — `git add app/i18n.py tests/test_i18n.py && git commit -m "feat: i18n catalog (en/pl/ru/uk)"`

---

### Task 6: z.ai client — vision extraction

**Files:**
- Create: `app/ai/client.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces: `@dataclass MedicineExtract: name, active_ingredient, form, dosage_pl, dosage_ru, dosage_uk, dosage_en, description_pl, description_ru, description_uk, description_en, expiry_date: str | None, multiple: bool = False`; `async extract_medicine(settings, images: list[bytes]) -> MedicineExtract | None` — POSTs to `{settings.zai_base_url}/chat/completions` with data-URL images, model `settings.zai_vision_model`; returns an extract with `multiple=True` when the photo shows several packages (spec: never guess — caller must ask for separate photos or a barcode photo); returns None on HTTP error, non-JSON, or missing `name` (when not multiple). `parse_extraction(text: str) -> MedicineExtract | None` is a separate pure function (tests target this; network function tested via mock).

- [ ] **Step 1: Write failing tests**

`tests/test_extract.py`:

```python
import json, httpx, pytest
from app.config import Settings
from app.ai.client import parse_extraction, extract_medicine

RAW = {
    "name": "Paracetamol 500 mg",
    "active_ingredient": "paracetamol",
    "form": "tablets",
    "dosage_pl": "1 tabletka do 3 razy dziennie",
    "dosage_ru": "1 таблетка до 3 раз в день",
    "dosage_uk": "1 таблетка до 3 разів на день",
    "dosage_en": "1 tablet up to 3x daily",
    "description_pl": "Lek na ból i gorączkę.",
    "description_ru": "Обезболивающее и жаропонижающее.",
    "description_uk": "Знеболювальне та жарознижуюче.",
    "description_en": "Pain and fever relief.",
    "expiry_date": "2027-03",
}

def test_parse_ok():
    e = parse_extraction(json.dumps(RAW))
    assert e.name == "Paracetamol 500 mg"
    assert e.expiry_date == "2027-03"
    assert e.dosage_pl == "1 tabletka do 3 razy dziennie"

def test_parse_wrapped_in_markdown():
    e = parse_extraction("```json\n" + json.dumps(RAW) + "\n```")
    assert e is not None and e.name == "Paracetamol 500 mg"

def test_parse_garbage_returns_none():
    assert parse_extraction("sorry I cannot") is None

def test_parse_missing_name_returns_none():
    e = parse_extraction(json.dumps({"description_en": "x"}))
    assert e is None

def test_parse_multiple_packages():
    e = parse_extraction(json.dumps({"multiple": True, "items": 3}))
    assert e is not None and e.multiple is True

@pytest.mark.asyncio
async def test_extract_medicine_http(monkeypatch):
    def fake_post(url, **kw):
        content = {"choices": [{"message": {"content": json.dumps(RAW)}}]}
        return httpx.Response(200, json=content, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    s = Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)
    e = await extract_medicine(s, [b"img"])
    assert e.name == "Paracetamol 500 mg"

@pytest.mark.asyncio
async def test_extract_medicine_http_error(monkeypatch):
    def fake_post(url, **kw):
        raise httpx.ConnectError("boom")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    s = Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)
    assert await extract_medicine(s, [b"img"]) is None
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL

- [ ] **Step 3: Implement `app/ai/client.py`**

```python
import base64, json, re
from dataclasses import dataclass
import httpx

PROMPT = (
    "You are reading a photo of ONE medicine package. First: if the photo shows more than one "
    "package/box, reply ONLY with {\"multiple\": true} — never guess which one is meant.\n"
    "Otherwise reply with RAW JSON (no markdown, no commentary) with exactly these keys: "
    "name, active_ingredient, form, dosage_pl, dosage_ru, dosage_uk, dosage_en, "
    "description_pl, description_ru, description_uk, description_en, expiry_date.\n"
    "dosage_*: how to take it (e.g. '1 tablet 2x daily') in the given language. "
    "description_*: one short sentence 'what it is for' in the given language. "
    "expiry_date: 'YYYY-MM-DD' if visible, else 'YYYY-MM', else null. "
    "If a value is unknown use '' (or null for expiry_date)."
)

@dataclass
class MedicineExtract:
    name: str
    active_ingredient: str
    form: str
    dosage_pl: str
    dosage_ru: str
    dosage_uk: str
    dosage_en: str
    description_pl: str
    description_ru: str
    description_uk: str
    description_en: str
    expiry_date: str | None
    multiple: bool = False

def parse_extraction(text: str) -> MedicineExtract | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if data.get("multiple"):
        return MedicineExtract(name="", active_ingredient="", form="",
                               dosage_pl="", dosage_ru="", dosage_uk="", dosage_en="",
                               description_pl="", description_ru="", description_uk="",
                               description_en="", expiry_date=None, multiple=True)
    if not data.get("name"):
        return None
    exp = data.get("expiry_date") or None
    return MedicineExtract(
        name=str(data["name"]), active_ingredient=data.get("active_ingredient", "") or "",
        form=data.get("form", "") or "",
        dosage_pl=data.get("dosage_pl", "") or "", dosage_ru=data.get("dosage_ru", "") or "",
        dosage_uk=data.get("dosage_uk", "") or "", dosage_en=data.get("dosage_en", "") or "",
        description_pl=data.get("description_pl", "") or "", description_ru=data.get("description_ru", "") or "",
        description_uk=data.get("description_uk", "") or "", description_en=data.get("description_en", "") or "",
        expiry_date=exp)

async def extract_medicine(settings, images: list[bytes]) -> MedicineExtract | None:
    content = [{"type": "text", "text": PROMPT}]
    for img in images:
        b64 = base64.b64encode(img).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    payload = {"model": settings.zai_vision_model,
               "messages": [{"role": "user", "content": content}]}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{settings.zai_base_url}/chat/completions",
                             json=payload, headers={"Authorization": f"Bearer {settings.zai_api_key}"})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None
    return parse_extraction(text)
```

- [ ] **Step 4: Run tests** — Expected: PASS
- [ ] **Step 5: Commit** — `git add app/ai/client.py tests/test_extract.py && git commit -m "feat: z.ai vision extraction client"`

---

### Task 7: z.ai text interpreter (intents + symptom query)

**Files:**
- Create: `app/ai/interpret.py`
- Test: `tests/test_interpret.py`

**Interfaces:**
- Produces: `@dataclass Intent: action: str, medicine_query: str, amount: float, symptom: str` with `action ∈ {"take", "opened", "query_qty", "expiring", "symptom", "unknown"}`; `parse_intent(text: str) -> Intent | None` (pure); `async interpret(settings, text: str) -> Intent` — calls `{settings.zai_base_url}/chat/completions` with `settings.zai_text_model`, falls back to `Intent(action="unknown")` on any failure.

- [ ] **Step 1: Write failing tests**

```python
import json, httpx, pytest
from app.config import Settings
from app.ai.interpret import parse_intent, interpret

def test_take():
    i = parse_intent('{"action":"take","medicine_query":"paracetamol","amount":1,"symptom":""}')
    assert (i.action, i.medicine_query, i.amount) == ("take", "paracetamol", 1)

def test_symptom():
    i = parse_intent('{"action":"symptom","medicine_query":"","amount":1,"symptom":"headache"}')
    assert i.action == "symptom" and i.symptom == "headache"

def test_garbage():
    assert parse_intent("hello") is None

@pytest.mark.asyncio
async def test_interpret_fallback():
    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "???"}}]}
    async def fake_post(url, **kw): return FakeResp()
    monkey = pytest.MonkeyPatch()
    monkey.setattr(httpx.AsyncClient, "post", staticmethod(fake_post))
    s = Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)
    assert interpret.__name__ == "interpret"
    i = await interpret(s, "???")
    assert i.action == "unknown"
    monkey.undo()
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL

- [ ] **Step 3: Implement `app/ai/interpret.py`**

```python
import json, re
from dataclasses import dataclass
import httpx

PROMPT = (
    "Classify the user's message about their home medicine cabinet. Reply ONLY with JSON: "
    '{"action":"take|opened|query_qty|expiring|symptom|unknown","medicine_query":"<which medicine, lowercase, or empty>","amount":<number, default 1>,"symptom":"<symptom if any, in English>"}\n'
    'Examples: "took 2 ibuprofen" -> take; "открыл сироп" -> opened; "сколько парацетамола?" -> query_qty; '
    '"что скоро истекает?" -> expiring; "болит голова, что есть?" -> symptom; greetings -> unknown.'
)

@dataclass
class Intent:
    action: str
    medicine_query: str = ""
    amount: float = 1
    symptom: str = ""

VALID = {"take", "opened", "query_qty", "expiring", "symptom", "unknown"}

def parse_intent(text: str) -> Intent | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if d.get("action") not in VALID:
        return None
    return Intent(action=d["action"], medicine_query=str(d.get("medicine_query", "")).lower(),
                  amount=float(d.get("amount", 1) or 1), symptom=str(d.get("symptom", "")))

async def interpret(settings, text: str) -> Intent:
    payload = {"model": settings.zai_text_model,
               "messages": [{"role": "system", "content": PROMPT},
                            {"role": "user", "content": text}]}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{settings.zai_base_url}/chat/completions",
                             json=payload, headers={"Authorization": f"Bearer {settings.zai_api_key}"})
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return Intent("unknown")
    return parse_intent(content) or Intent("unknown")
```

- [ ] **Step 4: Run tests** — Expected: PASS
- [ ] **Step 5: Commit** — `git add app/ai/interpret.py tests/test_interpret.py && git commit -m "feat: intent interpreter for Telegram messages"`

---

### Task 8: Telegram messages, keyboards, approval store

**Files:**
- Create: `app/bot/notify.py`, `app/bot/users.py`
- Test: `tests/test_notify.py`, `tests/test_users.py`

**Interfaces:**
- Produces: `users.py`: `is_allowed(conn, tg_id) -> bool`, `is_admin(settings, tg_id) -> bool`, `request_approval(conn, settings, bot, tg_id, name)` (inserts `role='pending'` if new, messages admin with approve/decline inline keyboard, callback data `approve:<tg_id>` / `decline:<tg_id>`), `approve(conn, tg_id)` / `decline(conn, tg_id)`. `notify.py`: `alert_text(lang, alert, med_row) -> str` and `alert_keyboard(alert) -> InlineKeyboardMarkup` (expiry kinds → [Discarded ✓ `discard:<id>`, Snooze 1 month `snooze_expiry:<id>`]; opened kinds → [Discarded ✓, Snooze 1 week `snooze_opened:<id>`]; low stock → [Add to shopping list `addlist:<id>:`]); `callback_to_action(data: str) -> tuple[str, int]` mapping `discard:/snooze_expiry:/snooze_opened:/addlist:` prefixes.

- [ ] **Step 1: Write failing tests**

`tests/test_users.py`:

```python
from app.db import init_db
from app.bot.users import is_allowed, approve, decline

def conn_with():
    return init_db(":memory:")

def test_pending_not_allowed():
    c = conn_with()
    c.execute("INSERT INTO allowed_users (telegram_id, role) VALUES (5, 'pending')")
    assert not is_allowed(c, 5)

def test_approve():
    c = conn_with()
    c.execute("INSERT INTO allowed_users (telegram_id, role) VALUES (5, 'pending')")
    approve(c, 5)
    assert is_allowed(c, 5)
    decline(c, 5)
    assert not is_allowed(c, 5)
```

`tests/test_notify.py`:

```python
from app.services.alerts import Alert
from app.bot.notify import alert_text, alert_keyboard, callback_to_action

ALERT = Alert("expiry_soon", 3, "Paracetamol", 7)

def test_alert_text():
    s = alert_text("en", ALERT, {"expiry_date": "2026-10-13", "quantity": 10, "unit": "pieces"})
    assert "Paracetamol" in s and "7" in s

def test_all_langs_have_text():
    for lang in ("en", "pl", "ru", "uk"):
        assert "Paracetamol" in alert_text(lang, ALERT, {"expiry_date": "2026-10-13"})

def test_keyboard_expiry():
    kb = alert_keyboard(Alert("expiry_soon", 3, "X", 7))
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "discard:3" in datas and "snooze_expiry:3" in datas

def test_keyboard_low_stock():
    kb = alert_keyboard(Alert("low_stock", 3, "X", 2))
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert datas == ["addlist:3:"]

def test_callback_parse():
    assert callback_to_action("snooze_opened:7") == ("snooze_opened", 7)
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL

- [ ] **Step 3: Implement `app/bot/users.py`**

```python
import sqlite3
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

def is_admin(settings, tg_id: int) -> bool:
    return tg_id == settings.admin_telegram_id

def is_allowed(conn: sqlite3.Connection, tg_id: int) -> bool:
    row = conn.execute("SELECT role FROM allowed_users WHERE telegram_id=?", (tg_id,)).fetchone()
    return row is not None and row["role"] == "member"

async def request_approval(conn, settings, bot: Bot, tg_id: int, name: str):
    conn.execute("INSERT OR IGNORE INTO allowed_users (telegram_id, name, role) VALUES (?,?, 'pending')",
                 (tg_id, name))
    conn.commit()
    kb = InlineKeyboardBuilder()
    kb.button(text="✅", callback_data=f"approve:{tg_id}")
    kb.button(text="❌", callback_data=f"decline:{tg_id}")
    await bot.send_message(settings.admin_telegram_id,
                           f"User {name} ({tg_id}) asks for access.", reply_markup=kb.as_markup())

def approve(conn, tg_id: int):
    conn.execute("UPDATE allowed_users SET role='member' WHERE telegram_id=?", (tg_id,))
    conn.commit()

def decline(conn, tg_id: int):
    conn.execute("DELETE FROM allowed_users WHERE telegram_id=?", (tg_id,))
    conn.commit()
```

`app/bot/notify.py`:

```python
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.alerts import Alert
from app.i18n import t

def alert_text(lang: str, alert: Alert, med: dict) -> str:
    if alert.kind == "expiry_soon":
        return t(lang, "expires_in_days", name=alert.name, days=alert.days)
    if alert.kind == "expiry_today":
        return t(lang, "expires_today", name=alert.name)
    if alert.kind == "expired":
        return t(lang, "expired_days_ago", name=alert.name, days=-alert.days)
    if alert.kind == "opened_soon":
        return t(lang, "discard_soon", name=alert.name, opened=med.get("opened_at", ""))
    if alert.kind == "opened_today":
        return t(lang, "discard_today", name=alert.name, opened=med.get("opened_at", ""))
    if alert.kind == "low_stock":
        return t(lang, "low_stock", name=alert.name, qty=alert.days)
    return t(lang, "last_dose", name=alert.name)

def alert_keyboard(alert: Alert):
    kb = InlineKeyboardBuilder()
    if alert.kind.startswith("expiry"):
        kb.button(text="🗑", callback_data=f"discard:{alert.medicine_id}")
        kb.button(text="⏰", callback_data=f"snooze_expiry:{alert.medicine_id}")
    elif alert.kind.startswith("opened"):
        kb.button(text="🗑", callback_data=f"discard:{alert.medicine_id}")
        kb.button(text="⏰", callback_data=f"snooze_opened:{alert.medicine_id}")
    else:
        kb.button(text="🛒", callback_data=f"addlist:{alert.medicine_id}:")
    return kb.as_markup()

def callback_to_action(data: str) -> tuple[str, int]:
    action, mid = data.split(":", 1)
    return action, int(mid)
```

- [ ] **Step 4: Run tests** — Expected: PASS
- [ ] **Step 5: Commit** — `git add app/bot tests/test_notify.py tests/test_users.py && git commit -m "feat: telegram alert formatting, keyboards, approval store"`

---

### Task 9: Telegram bot router (commands, conversation, callbacks)

**Files:**
- Create: `app/bot/router.py`
- Test: `tests/test_bot_logic.py`

**Interfaces:**
- Consumes: `MedicineService`, `app.ai.interpret.interpret`, `app.bot.users.*`, `app.bot.notify.*`, `app.i18n.t/detect_lang`.
- Produces: `build_router(conn, settings, services) -> aiogram.Router` where `services` is a dict `{"medicines": MedicineService}`. Handlers: `/start` (approval flow); free text → intent dispatch; `take` → find medicine by `name LIKE %query%` / active_ingredient; 0 matches → `no_match`, >1 → `which_one` + buttons `pick:<id>:<amount>`; 1 match → `take_dose`, reply `took` (or `last_dose` when quantity hits 0) and set `low_stock_notified=1` when ≤ threshold via direct UPDATE; `symptom` → search `description_*` columns case-insensitively against translated symptom terms supplied by AI (match in any of the 4 description languages + name + active_ingredient), reply `symptom_found` + lines "name — qty unit (usable/expired)"; `query_qty` → `took`-style reply; `expiring` → list within 7 days; `opened` → `mark_opened(today)`. Callbacks: `approve:`, `decline:`, `discard:`, `snooze_expiry:` (sets `snooze_expiry_until = today + 30d`), `snooze_opened:` (+7d), `pick:`, `addlist:` (Phase 1: append to `events` note 'shopping_list' + ack `added_to_list`). Pure helpers exported for tests: `match_medicines(conn, query) -> list[row]`, `symptom_matches(conn, symptom) -> list[row]`, `describe_matches(rows, lang) -> str`.

- [ ] **Step 1: Write failing tests**

`tests/test_bot_logic.py`:

```python
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.bot.router import match_medicines, symptom_matches, describe_matches

def make(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    svc = MedicineService(conn)
    a = svc.add({"name": "Paracetamol 500", "quantity": 10,
                 "description_en": "Pain and fever relief.",
                 "description_pl": "Lek na ból i gorączkę."})
    b = svc.add({"name": "Paracetamol kids", "quantity": 5})
    return conn, svc, a, b

def test_match_one(tmp_path):
    conn, svc, a, b = make(tmp_path)
    assert [r["id"] for r in match_medicines(conn, "500")] == [a]

def test_match_two_ambiguous(tmp_path):
    conn, svc, a, b = make(tmp_path)
    assert len(match_medicines(conn, "paracetamol")) == 2

def test_symptom_pl(tmp_path):
    conn, svc, a, b = make(tmp_path)
    assert [r["id"] for r in symptom_matches(conn, "headache")] == [a]

def test_describe(tmp_path):
    conn, svc, a, b = make(tmp_path)
    rows = match_medicines(conn, "paracetamol")
    s = describe_matches(rows, "en")
    assert "Paracetamol 500" in s and "10 pieces" in s
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL

- [ ] **Step 3: Implement `app/bot/router.py`** — full implementation with the handlers and helpers listed above. Core helpers:

```python
import datetime
import sqlite3
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings
from app.services.medicine_service import MedicineService
from app.ai.interpret import interpret, Intent
from app.bot.users import is_allowed, is_admin, request_approval, approve, decline
from app.i18n import t, detect_lang
from app.bot.notify import callback_to_action

def match_medicines(conn: sqlite3.Connection, query: str) -> list:
    q = f"%{query.strip().lower()}%"
    return conn.execute(
        "SELECT * FROM medicines WHERE lower(name) LIKE ? OR lower(active_ingredient) LIKE ? "
        "ORDER BY id", (q, q)).fetchall()

def symptom_matches(conn: sqlite3.Connection, symptom: str) -> list:
    q = f"%{symptom.lower()}%"
    return conn.execute(
        "SELECT DISTINCT * FROM medicines WHERE lower(name) LIKE ? OR lower(active_ingredient) LIKE ? "
        "OR lower(description_en) LIKE ? OR lower(description_pl) LIKE ? "
        "OR lower(description_ru) LIKE ? OR lower(description_uk) LIKE ?",
        (q, q, q, q, q, q)).fetchall()

def describe_matches(rows, lang: str) -> str:
    lines = []
    for r in rows:
        lines.append(f"• {r['name']} — {int(r['quantity'])} {r['unit']}")
    return "\n".join(lines)
```

(Handler wiring: `symptom` also translates `intent.symptom` to PL/RU/UK via one extra `interpret`-style AI call implemented as `async symptom_terms(settings, symptom) -> list[str]` in this file — calls z.ai text model with prompt "Translate this symptom to Polish, Russian, Ukrainian. Reply JSON: {\"pl\":\"...\",\"ru\":\"...\",\"uk\":\"...\"}" — then unions `symptom_matches` over all terms, dedup by id. `take` handler decrements via `MedicineService.take_dose`, sets `low_stock_notified=1` with a direct UPDATE when `quantity <= low_stock_threshold`, and replies `took`/`last_dose`. `pick:` callback re-runs the take/opened flow for the chosen id, storing pending action in-memory dict `{(chat_id): (action, amount)}`.)

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_bot_logic.py -v` → PASS
- [ ] **Step 5: Commit** — `git add app/bot/router.py tests/test_bot_logic.py && git commit -m "feat: telegram router with intents, symptom search, callbacks"`

---

### Task 10: Scheduler — daily alerts + AI retry + backup

**Files:**
- Create: `app/services/scheduler.py`, `app/services/backup.py`
- Test: `tests/test_scheduler.py`, `tests/test_backup.py`

**Interfaces:**
- Consumes: `evaluate`, `MedicineService`, `alert_text`, `alert_keyboard`.
- Produces: `async run_daily_check(conn, settings, bot: Bot, now_date: str | None = None) -> int` — evaluates alerts, sends each to admin with `alert_text`/`alert_keyboard` (admin lang from `allowed_users.lang`, default `en`), sets `low_stock_notified=1` after sending low-stock alerts, returns count sent; `schedule_jobs(conn, settings, bot, scheduler)` — adds cron job at `settings.daily_check_hour`, hourly AI-retry job, nightly backup job; `backup.py`: `run_backup(db_path: str, backup_dir: str, keep_days: int) -> str` (SQLite `conn.backup()` into `backup_dir/hub-YYYY-MM-DD.db.gz`, deletes files older than keep_days, returns backup path).

- [ ] **Step 1: Write failing tests**

`tests/test_backup.py`:

```python
import gzip, os
from app.db import init_db
from app.services.backup import run_backup

def test_backup_creates_gzip(tmp_path):
    db = str(tmp_path / "hub.db")
    init_db(db)
    out = run_backup(db, str(tmp_path / "bak"), keep_days=14)
    assert os.path.exists(out)
    with gzip.open(out, "rb") as f:
        head = f.read(16)
    assert b"SQLite" in head
```

`tests/test_scheduler.py`:

```python
from unittest.mock import AsyncMock
from app.config import Settings
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.scheduler import run_daily_check

def make_settings():
    return Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)

async def test_daily_check_sends_and_marks(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    MedicineService(conn).add({"name": "A", "expiry_date": "2026-10-06"})
    bot = AsyncMock()
    n = await run_daily_check(conn, make_settings(), bot, now_date="2026-10-06")
    assert n == 1
    bot.send_message.assert_awaited_once()
    assert conn.execute("SELECT expiry_date FROM medicines").fetchone()["expiry_date"] == "2026-10-06"

async def test_low_stock_notified_flag_set(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    MedicineService(conn).add({"name": "A", "quantity": 2, "low_stock_threshold": 3})
    bot = AsyncMock()
    await run_daily_check(conn, make_settings(), bot, now_date="2026-10-06")
    assert conn.execute("SELECT low_stock_notified FROM medicines").fetchone()["low_stock_notified"] == 1
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL

- [ ] **Step 3: Implement `app/services/backup.py`**

```python
import gzip, os, sqlite3, datetime

def run_backup(db_path: str, backup_dir: str, keep_days: int) -> str:
    os.makedirs(backup_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    out = os.path.join(backup_dir, f"hub-{today}.db.gz")
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(":memory:")
    src.backup(dst)
    with gzip.open(out, "wb") as f:
        for line in dst.iterdump():
            f.write((line + "\n").encode())
    cutoff = (datetime.date.today() - datetime.timedelta(days=keep_days)).isoformat()
    for name in os.listdir(backup_dir):
        day = name.replace("hub-", "").replace(".db.gz", "")
        if name.startswith("hub-") and day < cutoff:
            os.remove(os.path.join(backup_dir, name))
    return out
```

`app/services/scheduler.py`:

```python
import datetime, os
from aiologger import None  # not used; placeholder removed
```

(actual implementation — no third-party logger needed):

```python
import datetime, os, asyncio
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.alerts import evaluate
from app.services.backup import run_backup
from app.bot.notify import alert_text, alert_keyboard
from app.i18n import t

async def run_daily_check(conn, settings, bot: Bot, now_date: str | None = None) -> int:
    today = now_date or datetime.date.today().isoformat()
    row = conn.execute("SELECT lang FROM allowed_users WHERE telegram_id=?",
                       (settings.admin_telegram_id,)).fetchone()
    lang = row["lang"] if row and row["lang"] else "pl"
    sent = 0
    for a in evaluate(conn, today):
        med = conn.execute("SELECT * FROM medicines WHERE id=?", (a.medicine_id,)).fetchone()
        await bot.send_message(settings.admin_telegram_id,
                               alert_text(lang, a, dict(med)),
                               reply_markup=alert_keyboard(a))
        sent += 1
        if a.kind.startswith("low_stock"):
            conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?", (a.medicine_id,))
    conn.commit()
    return sent

async def retry_needs_ai(conn, settings, extract_fn):
    rows = conn.execute("SELECT * FROM medicines WHERE ai_status='needs_ai_data' AND photo_path IS NOT NULL").fetchall()
    for r in rows:
        with open(r["photo_path"], "rb") as f:
            ext = await extract_fn(settings, [f.read()])
        if ext:
            conn.execute(
                "UPDATE medicines SET name=?, expiry_date=?, ai_status='ok' WHERE id=?",
                (ext.name, ext.expiry_date, r["id"]))
    conn.commit()

def schedule_jobs(conn, settings, bot: Bot, scheduler: AsyncIOScheduler, extract_fn):
    scheduler.add_job(run_daily_check, "cron", hour=settings.daily_check_hour, minute=0,
                      args=[conn, settings, bot], id="daily_check", replace_existing=True)
    scheduler.add_job(retry_needs_ai, "interval", hours=1,
                      args=[conn, settings, extract_fn], id="ai_retry", replace_existing=True)
    scheduler.add_job(run_backup, "cron", hour=3, minute=0,
                      args=[os.path.join(settings.data_dir, "hub.db"),
                            os.path.join(settings.data_dir, "backups"),
                            settings.backup_keep_days],
                      id="backup", replace_existing=True)
```

- [ ] **Step 4: Run tests** — Expected: PASS
- [ ] **Step 5: Commit** — `git add app/services tests/test_scheduler.py tests/test_backup.py && git commit -m "feat: daily alert check, AI retry, automatic backups"`

---

### Task 11: Web UI — list, detail, i18n switcher

**Files:**
- Create: `app/web/routes.py`, `app/web/templates/base.html`, `app/web/templates/list.html`, `app/web/templates/detail.html`, `app/web/static/style.css`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `MedicineService`, `i18n.t`.
- Produces: `create_app(conn, settings, services) -> FastAPI` (defined fully in Task 13; this task adds the router `build_web_router(services) -> APIRouter` mounted at `/`). Routes here: `GET /` (list; search via `?q=`; groups "expiring within 7 days" first), `GET /medicine/{id}`, `POST /lang/{code}` (sets `lang` cookie, redirect `/`). Templates use `t()` via a Jinja global `T` bound per-request from the `lang` cookie.

- [ ] **Step 1: Write failing tests**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.web.routes import build_web_router
from app.web.app_factory import create_test_app

@pytest.mark.asyncio
async def test_list_shows_medicine(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    MedicineService(conn).add({"name": "Paracetamol", "quantity": 10})
    app = create_test_app(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/")
    assert r.status_code == 200 and "Paracetamol" in r.text

@pytest.mark.asyncio
async def test_lang_cookie_switch(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/lang/pl")
        r = await c.get("/")
    assert "Apteczka" in r.text or "apteczka" in r.text.lower()

@pytest.mark.asyncio
async def test_detail(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    mid = MedicineService(conn).add({"name": "A", "quantity": 4})
    app = create_test_app(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/medicine/{mid}")
    assert r.status_code == 200 and "A" in r.text
```

`app/web/app_factory.py` (test helper, reused by Task 13):

```python
import os
from fastapi import FastAPI
from app.web.routes import build_web_router

def create_test_app(conn, data_dir: str = "."):
    os.makedirs(os.path.join(data_dir, "photos"), exist_ok=True)
    app = FastAPI()
    app.state.data_dir = data_dir
    app.include_router(build_web_router({"medicines": None}, conn, default_lang="en", data_dir=data_dir))
    return app
```

(The `data_dir` parameter must exist from Task 11 onward — Task 12's photo-saving route writes under it. The optional `WEB_PASSWORD` login route from Task 13 is added to the real `create_app` only, not this test factory.)

- [ ] **Step 2: Run to verify failure** — Expected: FAIL

- [ ] **Step 3: Implement `app/web/routes.py`** — `build_web_router(services, conn, default_lang)` returning APIRouter with the three routes; Jinja2Templates from `app/web/templates`; helper `def T(request)` returning `lambda key, **kw: t(request.cookies.get("lang", default_lang), key, **kw)`; list view computes `expiring = [m for m in rows if m["expiry_date"] and 0 <= days_until <= 7]`, `others = rest`; detail view shows all fields + buttons (take dose form, mark opened, discard, re-read photo placeholder link, edit link). `base.html` includes `<meta name="viewport" content="width=device-width, initial-scale=1">`, lang switcher (4 flags as links to `/lang/<code>` with a POST form), and `{% block content %}`. `style.css`: minimal mobile-first (system font, max-width 480px, cards). The Polish `app_name` translation is `"Apteczka"` (from Task 5).

- [ ] **Step 4: Run tests** — Expected: PASS
- [ ] **Step 5: Commit** — `git add app/web tests/test_routes.py && git commit -m "feat: web list, detail, language switcher"`

---

### Task 12: Web UI — add flow with camera + AI extraction + actions

**Files:**
- Create: `app/web/templates/add.html`, `app/web/static/camera.js`
- Modify: `app/web/routes.py`, `app/web/templates/detail.html`, `app/web/templates/list.html`
- Test: `tests/test_routes_add.py`

**Interfaces:**
- Consumes: `extract_medicine`, `MedicineService.add`, `take_dose`, `mark_opened`, `discard`.
- Produces: routes `GET /add` (form with camera buttons + editable fields), `POST /extract` (multipart, ≤2 images → JSON extract, or `{"multiple": true}` when the photo shows several packages — the UI then shows "please photograph one box at a time or the barcode" and does NOT save; or `{"error": true}` on AI failure; saves photos to `DATA_DIR/photos/<uuid>.jpg`), `POST /add` (form fields → `MedicineService.add`; **expiry_date is required** — missing/empty expiry returns HTTP 400 with the form re-rendered and the expiry field highlighted, per spec; if extract failed earlier, `ai_status='needs_ai_data'` + `photo_path`), `POST /medicine/{id}/take` (amount from form), `POST /medicine/{id}/open`, `POST /medicine/{id}/discard`, `POST /medicine/{id}/reread` (runs extraction now, updates row), all redirect to `/medicine/{id}` or `/`. `camera.js`: on button tap, `getUserMedia({video: {facingMode: "environment"}})`, draw to `<canvas>`, `toBlob('image/jpeg', 0.8)`, append to form; file-input fallback if camera denied.

- [ ] **Step 1: Write failing tests**

```python
import io, json, pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.web.app_factory import create_test_app

def png():
    return io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64)

@pytest.mark.asyncio
async def test_add_manual(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/add", data={"name": "A", "quantity": "5", "expiry_date": "2027-01-01"},
                         follow_redirects=True)
        assert r.status_code == 200
    rows = conn.execute("SELECT * FROM medicines").fetchall()
    assert rows[0]["name"] == "A" and rows[0]["ai_status"] == "ok"

@pytest.mark.asyncio
async def test_add_requires_expiry(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/add", data={"name": "A", "quantity": "5", "expiry_date": ""})
    assert r.status_code == 400
    assert conn.execute("SELECT COUNT(*) c FROM medicines").fetchone()["c"] == 0

@pytest.mark.asyncio
async def test_extract_multiple_packages(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    fake = AsyncMock(return_value=AsyncMock(name="", multiple=True, expiry_date=None,
                          active_ingredient="", form="",
                          dosage_pl="", dosage_ru="", dosage_uk="", dosage_en="",
                          description_pl="", description_ru="", description_uk="", description_en=""))
    with patch("app.web.routes.extract_medicine", fake):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/extract", files=[("images", ("a.jpg", png(), "image/jpeg"))])
    assert json.loads(r.text) == {"multiple": True}

@pytest.mark.asyncio
async def test_extract_with_mocked_ai(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    fake = AsyncMock(return_value=AsyncMock(name="X", expiry_date="2027-01-01", multiple=False,
                          active_ingredient="", form="",
                          dosage_pl="", dosage_ru="", dosage_uk="", dosage_en="",
                          description_pl="", description_ru="", description_uk="", description_en=""))
    with patch("app.web.routes.extract_medicine", fake):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/extract", files=[("images", ("a.jpg", png(), "image/jpeg"))])
    assert r.status_code == 200
    assert json.loads(r.text)["name"] == "X"

@pytest.mark.asyncio
async def test_take_dose_route(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    mid = MedicineService(conn).add({"name": "A", "quantity": 10})
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(f"/medicine/{mid}/take", data={"amount": "2"}, follow_redirects=True)
    assert r.status_code == 200
    assert conn.execute("SELECT quantity FROM medicines WHERE id=?", (mid,)).fetchone()["quantity"] == 8
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL

- [ ] **Step 3: Implement routes + templates + camera.js** per interfaces above. `POST /extract` reads `UploadFile`s, validates content-type startswith `image/`, max 2, size ≤ 8 MB each; calls `extract_medicine(settings, [await f.read() ...])`; on success also writes first photo to `photos/` dir under `data_dir` and returns `{**asdict(ext), "photo_saved": path}`; on failure returns JSON `{"error": true}` with status 200 (form stays usable). `POST /add` includes hidden `photo_saved` field when present. `add.html`: two "camera" slots, JS fills hidden file inputs; extracted fields populate the form via JS; Save submits to `/add`. `detail.html` gets forms posting to the action routes.

- [ ] **Step 4: Run tests** — Expected: PASS
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: add-medicine flow with camera capture and AI extraction"`

---

### Task 13: Application assembly (lifespan: bot + scheduler + static)

**Files:**
- Create: `app/main.py`, `app/web/app_factory.py` (final version)
- Modify: `app/web/routes.py` (optional `WEB_PASSWORD` middleware)
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `create_app(settings) -> FastAPI` — opens/creates SQLite at `DATA_DIR/hub.db`, builds `MedicineService`, mounts web router + static files at `/static`, and in a FastAPI `lifespan` starts: aiogram `Bot` + `Dispatcher` (includes router from Task 9) via `asyncio.create_task(dp.start_polling(bot))`, `AsyncIOScheduler` with `schedule_jobs(...)`, seeds admin into `allowed_users` (role member), stops both on shutdown. Optional password middleware: if `settings.web_password`, require basic-auth cookie set via `GET /login` form.

- [ ] **Step 1: Write failing test**

```python
import pytest
from app.config import Settings
from app.main import create_app

def test_create_app_smoke(tmp_path):
    s = Settings("k", "http://x", "m", "m2", "", 0, 9, "", str(tmp_path), 14)
    app = create_app(s)
    assert app.state.conn is not None
    assert app.state.services["medicines"] is not None

def test_admin_seeded(tmp_path):
    s = Settings("k", "http://x", "m", "m2", "", 42, 9, "", str(tmp_path), 14)
    app = create_app(s)
    row = app.state.conn.execute("SELECT * FROM allowed_users WHERE telegram_id=42").fetchone()
    assert row is not None and row["role"] == "member"
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL
- [ ] **Step 3: Implement `app/main.py`** per interfaces. Polling task guarded: if `settings.telegram_bot_token` empty, skip bot startup (web-only mode, keeps tests/dev simple) and log a warning. Lifespan cancels the polling task and calls `scheduler.shutdown()` on exit.
- [ ] **Step 4: Run tests** — `python -m pytest -v` (full suite) → PASS
- [ ] **Step 5: Commit** — `git add app tests && git commit -m "feat: app assembly with bot polling and scheduler lifespan"`

---

### Task 14: Docker packaging + deployment docs

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `docs/deploy.md`
- Test: manual smoke checklist

**Interfaces:**
- Consumes: `app.main.create_app`, uvicorn.
- Produces: runnable container; `docs/deploy.md` with Proxmox LXC + Docker install, BotFather token steps, VPN access note, restore command.

- [ ] **Step 1: Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
VOLUME ["/data"]
ENV DATA_DIR=/data
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Note: `app/main.py` must expose module-level `app = create_app(load_settings())` for this CMD.

- [ ] **Step 2: docker-compose.yml**

```yaml
services:
  homehub:
    build: .
    restart: unless-stopped
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
```

- [ ] **Step 3: Write `docs/deploy.md`** — sections: (1) create LXC (Debian 12, 1 GB RAM), install Docker via get.docker.com; (2) clone repo, `cp .env.example .env`, fill values — BotFather steps (`/newbot`, copy token), z.ai API key, admin Telegram ID (get from @userinfobot); (3) `docker compose up -d --build`; (4) open `http://<lxc-ip>:8000` over VPN, add to phone home screen; (5) message the bot, approve yourself; (6) restore: stop container, `gunzip -c data/backups/hub-DATE.db.gz > data/hub.db` (file is SQL dump), start container; (7) update: `git pull && docker compose up -d --build`.

- [ ] **Step 4: Full test suite + smoke**

Run: `python -m pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: docker packaging and deployment guide"
```

Manual smoke (post-deploy, from spec §10): add medicine by photo → confirm form → save → daily check fires Telegram alert → "took 1 X" via bot decrements → symptom query returns the medicine.
