"""Temporary diagnostic: show AI search terms + Tantum Verde DB row.

Run inside the container:
    docker compose exec homehub python /app/scripts/diag_symptom.py
"""
import asyncio
import os

from app.ai.client import suggest_by_name  # noqa: F401  (protocol check)
from app.bot.router import symptom_terms
from app.config import load_settings
from app.db import get_conn


async def main():
    s = load_settings()
    print("APP SETTINGS: base_url =", s.zai_base_url, "| text model =", s.zai_text_model)

    terms = await symptom_terms(s, "ból gardła")
    print("TERMS for 'ból gardła':", terms)

    db = os.path.join(s.data_dir, "hub.db")
    conn = get_conn(db)
    rows = conn.execute(
        "SELECT id, name, description_pl, description_en, description_ru "
        "FROM medicines WHERE name LIKE '%Tantum%' OR name LIKE '%gardła%'"
    ).fetchall()
    if not rows:
        print("DB: no Tantum/gardła rows found")
    for r in rows:
        print("DB:", dict(r))


if __name__ == "__main__":
    asyncio.run(main())
