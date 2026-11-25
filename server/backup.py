"""Encrypted daily backups of the main database (2026-11-26).

What is backed up: only server/data/app.db (accounts, ranks, credits, plans, results, friends...).
What is NOT: recording audio/video, profile photos, and the voice fingerprints (server/biometric.py keeps those in a
separate database that is never backed up), so the most sensitive data has no extra copies anywhere.

  * A consistent copy is made with SQLite's online backup (safe while the server runs), compressed, then encrypted
    with AES-256-GCM. The key is its own file (SC_BACKUP_KEY_FILE): keep a copy of it somewhere safe and OFF the
    server, or the backups cannot be opened.
  * One backup a day, kept KEEP_DAYS days; older files are deleted, so deleted accounts leave the backups within 30 days.
  * Put SC_BACKUP_DIR on another disk or cloud storage in production: a backup on the same disk dies with it.

Restore (with the server stopped):   python -m server.backup restore server/data/backups/app-2026-11-26.db.enc
List backups:                       python -m server.backup list
"""

import gzip
import os
import sqlite3
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data"
DIR = Path(os.environ.get("SC_BACKUP_DIR", DATA / "backups"))
KEY_FILE = Path(os.environ.get("SC_BACKUP_KEY_FILE", DATA / "keys" / "backup.key"))
KEEP_DAYS = 30
MAGIC = b"SPKBK1"


def _key():
    if not KEY_FILE.exists():
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_bytes(os.urandom(32))
    k = KEY_FILE.read_bytes()
    assert len(k) == 32, "bad backup key file"
    return k


def _aes():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(_key())


def make(db_path=None, day=None):
    """Write today's encrypted backup (replaces one made earlier today). Returns its path."""
    from server import db
    src = Path(db_path or db.DB_PATH)
    day = day or date.today().isoformat()
    DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "copy.db"
        with sqlite3.connect(src) as a, sqlite3.connect(copy) as b:
            a.backup(b)
        b.close()
        plain = gzip.compress(copy.read_bytes(), 6)
    nonce = os.urandom(12)
    out = DIR / f"app-{day}.db.enc"
    part = out.with_suffix(".part")
    part.write_bytes(MAGIC + nonce + _aes().encrypt(nonce, plain, MAGIC + day.encode()))
    part.replace(out)
    prune()
    return out


def prune(today=None):
    """Delete backups older than KEEP_DAYS days."""
    limit = (today or date.today()) - timedelta(days=KEEP_DAYS)
    for f in DIR.glob("app-*.db.enc"):
        try:
            if date.fromisoformat(f.name[4:14]) < limit:
                f.unlink()
        except ValueError:
            pass


def read(path):
    """Decrypt a backup file and return the SQLite database bytes."""
    path = Path(path)
    raw = path.read_bytes()
    assert raw[:6] == MAGIC, "not a Speakoff backup"
    day = path.name[4:14]
    return gzip.decompress(_aes().decrypt(raw[6:18], raw[18:], MAGIC + day.encode()))


def restore(path, db_path=None):
    """Replace the database with a backup (server must be stopped). The current database is kept as .before-restore."""
    from server import db
    target = Path(db_path or db.DB_PATH)
    data = read(path)
    if target.exists():
        target.replace(target.with_name(target.name + f".before-restore-{int(time.time())}"))
    for extra in (target.with_name(target.name + "-wal"), target.with_name(target.name + "-shm")):
        extra.unlink(missing_ok=True)
    target.write_bytes(data)
    with sqlite3.connect(target) as c:                     # make sure it opens
        c.execute("SELECT COUNT(*) FROM users").fetchone()
    return target


def loop():
    """Background thread: a backup at start (if none today) and then once a day."""
    while True:
        try:
            if not (DIR / f"app-{date.today().isoformat()}.db.enc").exists():
                print("backup written:", make())
        except Exception as e:
            print("backup failed:", e)
        time.sleep(3600)


def start():
    threading.Thread(target=loop, daemon=True, name="backup").start()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "make":
        print(make())
    elif cmd == "restore" and len(sys.argv) > 2:
        print("restored into", restore(sys.argv[2]))
    else:
        for f in sorted(DIR.glob("app-*.db.enc")):
            print(f.name, f"{f.stat().st_size // 1024} KB", datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes"))
