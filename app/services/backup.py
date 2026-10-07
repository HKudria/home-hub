import gzip, os, shutil, sqlite3, datetime

def run_backup(db_path: str, backup_dir: str, keep_days: int) -> str:
    os.makedirs(backup_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    out = os.path.join(backup_dir, f"hub-{today}.db.gz")
    # Snapshot the DB via SQLite's backup API into a temp file, then gzip
    # the raw database bytes (so the gunzipped file is a usable SQLite db).
    tmp = out + ".tmp"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    dst.close()
    src.close()
    with open(tmp, "rb") as fin, gzip.open(out, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    os.remove(tmp)
    cutoff = (datetime.date.today() - datetime.timedelta(days=keep_days)).isoformat()
    for name in os.listdir(backup_dir):
        day = name.replace("hub-", "").replace(".db.gz", "")
        if name.startswith("hub-") and day < cutoff:
            os.remove(os.path.join(backup_dir, name))
    return out
