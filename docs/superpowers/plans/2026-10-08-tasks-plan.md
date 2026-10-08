# Phase 3 — Task Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Checkbox (`- [ ]`) syntax.

**Goal:** Shared family task tracker: web `/tasks` page + Telegram natural-language tasks, optional due dates and assignees (approved Telegram members), daily due/overdue digest via bot, full attribution.

**Spec:** `docs/superpowers/specs/2026-10-08-tasks-design.md`
**Patterns:** identical to Phase 2 — reuse service/route/i18n/bot conventions; Task 1 in-sandbox TDD (stdlib), Tasks 2–4 Docker-tested by user, then fix wave.

## Global Constraints

Same as Phase 2 (plain commits, no AI trailers; all strings via i18n ×4; web actor "web"; Unicode-fold matching in Python, not SQL `lower()`).

---

### Task 1: tasks schema + TaskService (in-sandbox TDD)

**Files:** Modify `app/db.py` (SCHEMA append), create `app/services/task_service.py`, test `tests/test_task_service.py`.

**Interfaces:** `TaskService(conn)`:
- `add_task(title, actor, due_date=None, assignee_id=None, assignee_name=None) -> Row` (title trimmed; empty/whitespace title → ValueError; due_date stored as given or None)
- `list_open() -> list[Row]` (due asc, NULLs last, then id)
- `list_done(limit=20)` (done_at desc)
- `complete(query, actor) -> Row | None` (isdigit→id among open; else Unicode-fold title match among open; sets done/done_by/done_at)
- `toggle(task_id, actor) -> Row | None` (done→reopen, else complete)
- `assign(task_id, telegram_id, name)`
- `due_and_overdue(today) -> list[Row]` (open, due_date NOT NULL, due_date <= today, due asc)
- `for_assignee(telegram_id, today) -> list[Row]` (open, assigned, due<=today)

DDL:
```sql
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  created_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  done INTEGER NOT NULL DEFAULT 0,
  done_by TEXT,
  done_at TEXT,
  due_date TEXT,
  assignee_id INTEGER,
  assignee_name TEXT
);
```

- [ ] Tests first (unittest): add + trim; empty title raises; list_open ordering (pin timestamps/due dates); complete by title (Unicode fold: "Żółtko"); complete by id; missing → None; toggle reopen; due_and_overdue boundary (due == today included, tomorrow excluded, done excluded); for_assignee filter. Run → FAIL → implement → PASS → full stdlib suite green.
- [ ] Commit: `feat: tasks schema and service`

---

### Task 2: Interpreter intents (Docker-tested)

**Files:** Modify `app/ai/interpret.py`, `tests/test_interpret.py`.

**Interfaces:** Intent gains `task_title: str = ""`, `due_date: str | None = None`, `assignee: str = ""`. VALID += `addtask`, `donetask`, `showtasks`. PROMPT teaches examples: "add task pay bills on friday" → addtask (task_title "pay bills", due_date ISO of next friday or null), "напомни Анне полить цветы завтра" → addtask + assignee "Anna" + due_date, "task pay bills is done" → donetask, "show tasks" → showtasks. parse: due_date must match `^\d{4}-\d{2}-\d{2}$` else None; tolerant like items.

- [ ] Tests: addtask parse (title/due/assignee); donetask; bad due_date → None; old tests unchanged. py_compile. Commit: `feat: task intents in message interpreter`

---

### Task 3: Bot handlers + daily digest + i18n (Docker-tested)

**Files:** Modify `app/bot/router.py`, `app/services/scheduler.py`, `app/i18n.py`, `tests/test_bot_logic.py`, `tests/test_scheduler.py`.

**Interfaces:**
- i18n ×4: `task_added` ("Task added: {title}"), `task_assigned_note` (" → {who}"), `task_unassigned_note` ("(could not match member '{who}' — left unassigned)"), `task_done` ("Done: {title} ✓"), `task_empty` ("No open tasks"), `task_list` ("Open tasks:"), `task_new_dm` ("New task from {who}: {title}{due}"), `task_due` (" due {date}"), `task_overdue` ("OVERDUE"), `task_digest` ("Tasks due:"), `nav_tasks` ("Tasks").
- Bot: addtask → assignee match against allowed_users members (approved only, name case-insensitive substring) → add_task → confirm `task_added` + `task_assigned_note`/`task_unassigned_note`; if assigned → `bot.send_message(assignee_id, t(assignee_lang_or_'pl', "task_new_dm", who=actor, title=..., due=" due "+due if due))` wrapped in try/except. donetask → complete → task_done/no_match. showtasks → `format_open_tasks(rows, lang)` (new exported pure helper: "" if empty else task_list + lines "• title — due X → name" with OVERDUE prefix when due < today) or task_empty.
- scheduler: new `run_task_digest(conn, settings, bot, today=None)` — rows = due_and_overdue(today); if none → 0; build digest text via format_open_tasks; send to admin + to each distinct assignee_id (their own for_assignee list, falling back to digest); per-send try/except; returns count. `schedule_jobs` adds it to the same daily cron (after daily_check — separate job, same hour).
- services dict gains "tasks": lazy `TaskService(conn)`.
- Tests: format_open_cases (en lines incl. OVERDUE prefix); run_task_digest with AsyncMock bot: 1 due unassigned → sends only to admin; assigned member → also to member.

- [ ] Implement + py_compile. Commit: `feat: tasks via telegram with daily due digest`

---

### Task 4: Web /tasks page (Docker-tested)

**Files:** Modify `app/web/routes.py`, `app/web/app_factory.py`, `app/web/templates/base.html`, `app/i18n.py`; create `app/web/templates/tasks.html`, `tests/test_routes_tasks.py`.

**Interfaces:**
- Routes: `GET /tasks` (open, done(20), members = allowed_users role='member' for dropdown); `POST /tasks/add` (fields title (required — 400 re-render like medicines), due_date (optional, full-date validated), assignee (member id, optional → resolve name)); `POST /tasks/complete/{id}` toggle; all 303 → /tasks.
- base.html nav: ☑ T('nav_tasks') → /tasks.
- tasks.html: add form (title text, due date input type=date, assignee select with members + "—"), open tasks with ✓ toggle forms, due badges (red OVERDUE when due < today, orange due == today — computed in template with today passed in context), done section with done_by, empty state (task_empty).
- i18n web keys ×4: `form_title` ("Title"), `form_due` ("Due date"), `form_assignee` ("Assignee"), `done_section` ("Done"), `task_added_by` ("added by {who}"), `task_done_by` ("done by {who}").
- Factory services dict gains "tasks": None; main.py registers TaskService(conn) (controller does this in integration commit).
- Tests (house style): add → row; add empty title → 400; complete toggle; page shows title; overdue badge class present (pass fixed today via monkeypatching? simplest: template receives `today` from route using date.today() — test asserts on a task with due_date 2020-01-01 → "OVERDUE" string present).

- [ ] Implement + py_compile + Jinja render smoke. Commit: `feat: tasks web page`

---

### Task 5: Integration + ship

- [ ] Controller: main.py services += "tasks": TaskService(conn) (single-line commit `chore: register task service in app assembly`)
- [ ] User Docker run → fix wave
- [ ] Manual smoke: add task with due date + assignee on web → bot digest fires (or simulate by setting due today) → donetask via bot
- [ ] Push; deploy; Phase 3 done

## Out of scope (future)

- Recurring tasks; sub-tasks; notification snoozes for tasks; per-member task privacy
