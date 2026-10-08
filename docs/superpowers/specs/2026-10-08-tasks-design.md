# Phase 3 — Family Task Tracker — Design

**Date:** 2026-10-08
**Parent spec:** 2026-10-06-home-hub-design.md (§5)
**Status:** Approved by user ("start it")

## Summary

One shared task list for the family: tasks with a title, optional due date, and optional assignee (an approved Telegram member). Due-date reminders go through the bot — to the admin and to each assigned member. Attribution (who created / who completed) like the shopping list.

## Data model

`tasks` table:

| field | notes |
|---|---|
| id | PK |
| title | trimmed, required |
| created_by / created_at | attribution |
| done / done_by / done_at | 0/1 + attribution on completion |
| due_date | nullable, `YYYY-MM-DD` |
| assignee_id | nullable — allowed_users.telegram_id |
| assignee_name | nullable — snapshot for display robustness |

## Service

`TaskService(conn)`:
- `add_task(title, actor, due_date=None, assignee_id=None, assignee_name=None) -> row` (trims, requires title)
- `list_open()` — open tasks, due-date ascending, NULLs last
- `list_done(limit=20)` — newest first
- `complete(query, actor) -> row | None` — numeric = id, else case-insensitive (Unicode fold) title match among open
- `assign(task_id, telegram_id, name)`; `due_and_overdue(today) -> list[Row]` — open tasks with due_date <= today
- `for_assignee(telegram_id, today)` — open tasks assigned to member, due <= today

## Interpreter

New intents: `addtask` (task_title, due_date `YYYY-MM-DD` or null, assignee name or empty), `donetask` (title in medicine_query), `showtasks`.

Examples taught to the AI: "add task pay bills on friday" (AI normalizes the date), "напомни Анне полить цветы завтра" → addtask + assignee Anna, "task pay bills is done" → donetask, "show tasks" → showtasks.

## Telegram

- addtask → match assignee name against allowed_users (case-insensitive substring); unmatched → task added unassigned with a note in the reply. If assigned → the assignee gets a DM "New task from <actor>: <title> (due ...)".
- donetask → complete → "Done: <title> ✓" (or no_match)
- showtasks → "Open tasks:" + lines "• title — due X → assignee" (or list_empty)
- Daily digest (scheduler, same cron as medicine check): open tasks due today or overdue → sent to admin AND to each assigned member (their own tasks); no digest if nothing due. Per-send try/except like medicine alerts.

New i18n keys ×4: `task_added`, `task_done`, `task_empty`, `task_list`, `task_new_dm` ("New task from {who}: {title}"), `task_due` ("due {date}"), `task_overdue` ("OVERDUE"), `task_digest` ("Tasks due:"), `nav_tasks` ("Tasks"), plus web labels (`form_title`, `form_due`, `form_assignee`, `done_section`, `feed_tadded`, `feed_tdone`, `assignee_unmatched` note).

## Web

- `/tasks` page (nav ☑ link): add form (title required, due date date-input, assignee dropdown from allowed_users members), open tasks with ✓ complete buttons, red "overdue" / orange "due today" badges, done section with attribution, activity via created/done fields.
- Routes: `GET /tasks`, `POST /tasks/add`, `POST /tasks/complete/{id}` (toggle), all 303 → `/tasks`. Assignee dropdown values = approved members' telegram ids (web actor attribution "web").

## Testing

TaskService: stdlib-unittest in-sandbox (dates, matching, digest queries). Interpreter/bot/web/scheduler: pytest, Docker run by user + fix wave (established flow).
