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
