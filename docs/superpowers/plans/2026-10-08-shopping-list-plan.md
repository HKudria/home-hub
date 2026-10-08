# Phase 2 — Shopping List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** One shared family shopping list, usable from the web app and the Telegram bot in natural language, with who-added/who-bought attribution and a working 🛒 low-stock button.

**Architecture:** New `shopping_items` SQLite table + `ShoppingService`; three new interpreter intents; bot handlers; `/shopping` web page. Follows all Phase 1 patterns (i18n ×4, actor attribution, tests-first).

**Tech Stack:** unchanged (FastAPI, SQLite, aiogram, httpx, pytest).

**Spec:** `docs/superpowers/specs/2026-10-08-shopping-list-design.md`

## Global Constraints

- Same as Phase 1 (plain commits, no AI trailers; sandbox: stdlib-only testing for Task 1; Docker run for the rest; 3.10-compatible code).
- One shared list — no per-person lists.
- Web actor name is `"web"`; Telegram actor is the sender's full name.
- New user-visible strings must exist in all 4 languages (en/pl/ru/uk, en fallback).

---

### Task 1: ShoppingService + schema (in-sandbox TDD)

**Files:**
- Modify: `app/db.py` (add table to SCHEMA)
- Create: `app/services/shopping_service.py`
- Test: `tests/test_shopping_service.py` (stdlib unittest)

**Interfaces:**
- Produces: `ShoppingService(conn)`:
  - `add_items(names: list[str], actor: str, from_medicine_id: int | None = None) -> list[str]` — trims, drops empties, skips case-insensitive duplicates of unbought items AND duplicate names within the call; returns actually-added names.
  - `list_unbought() -> list[Row]` (oldest first), `list_bought(limit: int = 20) -> list[Row]` (newest first).
  - `check_off(query: str, actor: str) -> Row | None` — numeric query = id, else case-insensitive name among unbought; sets bought=1, bought_by, bought_at=datetime('now').
  - `uncheck(item_id: int)`; `clear_bought() -> int`; `recent_activity(limit: int = 15) -> list[Row]` (bought first by bought_at desc then added_at desc, UNION-ish via two ordered queries is fine — simplest: `SELECT * FROM shopping_items ORDER BY COALESCE(bought_at, added_at) DESC LIMIT ?`).

- [ ] **Step 1: Write failing tests** — tests/test_shopping_service.py with cases: add single; add multiple with dedupe (whitespace, case-insensitive dup of unbought); list_unbought oldest first; check_off by name; check_off by id; check_off missing → None; uncheck; clear_bought returns count and empties bought; recent_activity ordering.
- [ ] **Step 2: Run `python3 -m unittest tests.test_shopping_service -v`** → FAIL (no module)
- [ ] **Step 3: Implement schema + service**
- [ ] **Step 4: Run** → PASS; full stdlib suite green
- [ ] **Step 5: Commit** `feat: shopping list schema and service`

Schema:
```sql
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
```

---

### Task 2: Interpreter intents (Docker-tested)

**Files:**
- Modify: `app/ai/interpret.py`, `tests/test_interpret.py`

**Interfaces:**
- `Intent` gains `items: list[str] = field(default_factory=list)` (keep other fields/defaults; `dataclasses.field` import needed).
- PROMPT adds: `'"add milk and bread" -> addlist with items ["milk","bread"]; "bought milk" -> bought with medicine_query "milk"; "show shopping list" / "что в списке?" -> showlist;'` and JSON schema gains `"items": [...]`.
- parse_intent: `items` = list of trimmed non-empty strings (default `[]`), tolerant of missing/malformed (wrap in try).
- VALID gains `addlist`, `bought`, `showlist`.

- [ ] **Step 1: Update tests** — extend existing parse tests: `{"action":"addlist","items":["milk"," bread"]}` → items == ["milk","bread"]; `{"action":"bought","medicine_query":"milk"}` → action bought; old asserts unchanged (take/unknown/symptom). New test: malformed items (`"items":"x"`, `"items":{}`) → `[]`.
- [ ] **Step 2: Implement; py_compile**
- [ ] **Step 3: Commit** `feat: shopping intents in message interpreter`

---

### Task 3: Bot handlers + i18n (Docker-tested)

**Files:**
- Modify: `app/bot/router.py`, `app/i18n.py`, `tests/test_bot_logic.py`

**Interfaces:**
- i18n keys ×4 (natural translations): `list_added` = "Added: {items}", `list_bought` = "Bought: {name} ✓", `list_empty` = "The shopping list is empty", `list_contents` = "Shopping list:", `nav_shopping` = "Shopping". Update `help_text` in all langs to include shopping examples ("add milk", "bought milk", "show shopping list").
- Bot free-text dispatch additions (services dict gains `"shopping": ShoppingService` — build_router signature unchanged, services passed in):
  - addlist → `added = svc.add_items(intent.items, actor)` → reply `list_added` with ", ".join(added) or `no_match` if nothing new (all dupes).
  - bought → `row = svc.check_off(intent.medicine_query, actor)` → `list_bought` or `no_match`.
  - showlist → unbought lines "• {name}" joined after `list_contents`; empty → `list_empty`.
- 🛒 `addlist:<id>:` callback: replace the events-note stub with `ShoppingService(conn).add_items([med["name"]], actor, from_medicine_id=id)` + reply `list_added`.
- Router construction: handlers use `services.get("shopping") or ShoppingService(conn)` (mirrors medicines lazy pattern).

- [ ] **Step 1: Add i18n keys + handler code; extend tests/test_bot_logic.py with pure-logic test: `format_list_contents(rows, lang)` helper (new, exported) → "Shopping list:\n• milk\n• bread" for en and empty-string rows → markers for list_empty path (test the helper, handlers stay thin)**
- [ ] **Step 2: py_compile; line-by-line i18n key/kwargs check**
- [ ] **Step 3: Commit** `feat: shopping list via telegram`

---

### Task 4: Web /shopping page (Docker-tested)

**Files:**
- Modify: `app/web/routes.py`, `app/web/app_factory.py`, `app/web/templates/base.html`, `tests/test_routes_add.py` (or new `tests/test_routes_shopping.py`)
- Create: `app/web/templates/shopping.html`

**Interfaces:**
- `build_web_router` and `create_test_app` services dict gains `"shopping"` (lazy `ShoppingService(conn)` fallback, same as medicines).
- Routes: `GET /shopping` (context: unbought, bought, activity, T, lang); `POST /shopping/add` (field `names`, comma-separated → svc.add_items(names.split(","), "web")); `POST /shopping/check/{id}` (toggle: bought → uncheck, else check_off(id, "web")); `POST /shopping/clear`. All POSTs redirect 303 → `/shopping`; unknown id → redirect anyway.
- base.html nav: link 🛒 T('nav_shopping') → /shopping (next to Add).
- shopping.html: add form (input name="names", placeholder T('search_placeholder')-style new key NOT needed — reuse `add_medicine`? no: add `list_placeholder` = "Add items, separated by commas" ×4), unbought as single-item forms with a checkbox-style button (☑), attribution line "{added_by} · {added_at date part}", bought section with bought_by attribution, Clear bought button (T('clear_bought') = "Clear bought" ×4), activity feed (T('activity') = "Recent activity" ×4).
- Tests (new tests/test_routes_shopping.py, style of test_routes_add.py): add items → redirect + rows exist; check toggles bought flag; clear removes bought rows; page GET 200 contains added name.

- [ ] **Step 1: Tests verbatim-first; implement routes/template; py_compile + Jinja render check**
- [ ] **Step 2: Commit** `feat: shopping list web page`

---

### Task 5: Integration + ship

- [ ] Full Docker suite: `docker compose -f docker-compose.dev.yml run --rm tests` (user runs) → fix wave if needed
- [ ] Manual smoke: web add → bot "bought milk" → 🛒 button adds → activity feed shows attribution
- [ ] Push; merge; deploy (`git pull && docker compose up -d --build`)

## Out of scope (future)

- Notifications when someone else checks off your item
- Quantity on shopping items
- Auto-add suggested staples
