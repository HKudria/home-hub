# Phase 2 — Shared Shopping List — Design

**Date:** 2026-10-08
**Parent spec:** 2026-10-06-home-hub-design.md (§4)
**Status:** Approved by user ("go with it")

## Summary

One shared shopping list for the whole family, available in the web app (`/shopping`) and through the Telegram bot in natural language (all 4 languages). Every item records who added it and who bought it (attribution history). The low-stock alert's 🛒 button becomes functional.

## Data model

`shopping_items` table:

| field | notes |
|---|---|
| id | PK |
| name | item name, trimmed |
| added_by | actor name (Telegram full name or "web") |
| added_at | ISO datetime (SQLite default now) |
| bought | 0/1 |
| bought_by / bought_at | set on check-off |
| from_medicine_id | nullable — set when added via low-stock button |

No per-person lists (user decision: one shared list). No notifications on others' check-offs — visible in the activity feed instead (future option).

## Service

`ShoppingService(conn)`:
- `add_items(names: list[str], actor, from_medicine_id=None) -> list[str]` — trims, drops empties, skips case-insensitive duplicates of already-unbought items; returns the names actually added.
- `list_unbought()` — oldest first.
- `list_bought(limit=20)` — most recent first.
- `check_off(query, actor) -> row | None` — by id (if numeric) or case-insensitive name match among unbought; sets bought/bought_by/bought_at.
- `uncheck(item_id)` — un-buys.
- `clear_bought() -> int` — deletes bought rows, returns count.

## Telegram

New interpreter intent actions (extend PROMPT): `addlist` (comma/newline separated `items`), `bought` (item name in medicine_query), `showlist`.

- "add milk and bread" → adds both → "Added: milk, bread"
- "bought milk" → checks off → "Bought: milk ✓" (or no_match if not on the list)
- "show shopping list" → "Shopping list:" + lines, or "The shopping list is empty"
- 🛒 low-stock callback → adds the medicine name to the list (from_medicine_id set) → "Added: …"

New i18n keys ×4: `list_added` ("Added: {items}"), `list_bought` ("Bought: {name} ✓"), `list_empty`, `list_contents`, `nav_shopping` ("Shopping"), extended `help_text` examples.

## Web

- `/shopping` page (nav link 🛒): add input (comma-separated = multiple items), unbought items as big checkboxes (checking = bought by "web"), bought items below with attribution, "Clear bought" button, recent-activity feed ("milk — added by Anna · bought by you/herman").
- Routes: `GET /shopping`, `POST /shopping/add` (names), `POST /shopping/check/{id}` (toggle), `POST /shopping/clear`. All redirect back to /shopping.

## Testing

Stdlib-unittest for the service (in-sandbox); pytest for interpreter/bot/web (Docker run by user, then fix wave — same flow as Phase 1).
