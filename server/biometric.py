"""Voice fingerprints (biometric data), kept apart from all other personal data (2026-11-26).

Only for players who gave separate, explicit consent (users.voice_consent = 1); used only by the anti-cheat voice check.
  * Made in memory from the answer that is being scored; no extra copy of the audio is ever created for it.
  * Irreversible, revocable template: the WavLM speaker vector is turned by a secret random rotation (a keyed
    orthogonal matrix) and stored at reduced precision. Comparing still works (a rotation keeps cosine similarity),
    but a leaked template is meaningless without the key, and changing the key cancels every old template.
  * Encrypted at rest with AES-256-GCM (a fresh nonce per template).
  * Separate: its own database file (biometric.db) with no names, emails or phone numbers. Rows are keyed by a
    pseudonymous ID (HMAC-SHA256 of the user id); only the key can link a row to a player.
  * The key lives in its own file (or SC_BIO_KEY_FILE, best outside the server disk in production), never in a database.
  * Kept: the newest KEEP templates per player; all are deleted at once when consent is withdrawn or the account is deleted.
"""

import hashlib
import hmac
import os
import sqlite3
import threading
import time
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"
BIO_DB = Path(os.environ.get("SC_BIO_DB", DATA / "biometric.db"))
KEY_FILE = Path(os.environ.get("SC_BIO_KEY_FILE", DATA / "keys" / "bio.key"))
KEEP = 10
DIM = 512                                     # microsoft/wavlm-base-plus-sv vector size

_lock = threading.Lock()
_cache = {}


def _keys():
    """96 random bytes: AES key | HMAC key | rotation seed. Created once."""
    with _lock:
        if "k" not in _cache:
            if not KEY_FILE.exists():
                KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
                KEY_FILE.write_bytes(os.urandom(96))
            raw = KEY_FILE.read_bytes()
            assert len(raw) == 96, "bad biometric key file"
            _cache["k"] = (raw[:32], raw[32:64], int.from_bytes(raw[64:], "big"))
        return _cache["k"]


def _rotation():
    if "r" not in _cache:
        seed = _keys()[2]
        q, r = np.linalg.qr(np.random.default_rng(seed).standard_normal((DIM, DIM)))
        _cache["r"] = (q * np.sign(np.diag(r))).astype(np.float32)
    return _cache["r"]


def pid(uid):
    return hmac.new(_keys()[1], f"user:{uid}".encode(), hashlib.sha256).hexdigest()


def protect(vector):
    """Raw speaker vector -> protected template (list of floats): rotated with the secret key, 16-bit precision."""
    v = np.asarray(vector, dtype=np.float32)
    if v.shape != (DIM,):
        raise ValueError("unexpected voice vector size")
    t = _rotation() @ v
    return (t / np.linalg.norm(t)).astype(np.float16).astype(np.float32).tolist()


def _db():
    BIO_DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(BIO_DB, timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS templates (pid TEXT NOT NULL, created REAL NOT NULL, nonce BLOB NOT NULL, "
              "data BLOB NOT NULL)")
    c.execute("CREATE INDEX IF NOT EXISTS t_pid ON templates(pid, created)")
    return c


def _aes():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(_keys()[0])


def add(uid, template):
    """Store one protected template (from protect()); keep only the newest KEEP."""
    p = pid(uid)
    nonce = os.urandom(12)
    blob = _aes().encrypt(nonce, np.asarray(template, dtype=np.float16).tobytes(), p.encode())
    with _db() as c:
        c.execute("INSERT INTO templates (pid, created, nonce, data) VALUES (?,?,?,?)", (p, time.time(), nonce, blob))
        c.execute("DELETE FROM templates WHERE pid=? AND rowid NOT IN (SELECT rowid FROM templates WHERE pid=? "
                  "ORDER BY created DESC LIMIT ?)", (p, p, KEEP))


def recent(uid, n=KEEP):
    """The player's newest templates, oldest first (decrypted, still protected)."""
    p = pid(uid)
    aes = _aes()
    with _db() as c:
        rows = c.execute("SELECT nonce, data FROM templates WHERE pid=? ORDER BY created DESC LIMIT ?", (p, n)).fetchall()
    return [np.frombuffer(aes.decrypt(nonce, data, p.encode()), dtype=np.float16).astype(np.float32).tolist()
            for nonce, data in reversed(rows)]


def delete_user(uid):
    with _db() as c:
        c.execute("DELETE FROM templates WHERE pid=?", (pid(uid),))
    with _db() as c:
        c.execute("VACUUM")                          # do not leave deleted templates in free pages


def migrate(main_db):
    """Move fingerprints from the old voice_prints table (main database) into this store, then wipe them there.
    Only players who consented are kept; the rest are dropped."""
    import json
    try:
        rows = main_db.all_("SELECT v.user_id, v.created, v.emb, u.voice_consent FROM voice_prints v "
                            "JOIN users u ON u.id=v.user_id ORDER BY v.created")
    except Exception:
        return 0
    moved = 0
    for r in rows:
        if r["voice_consent"] == 1:
            add(r["user_id"], protect(json.loads(r["emb"])))
            moved += 1
    if rows:
        main_db.run("DELETE FROM voice_prints")
        main_db.run("VACUUM")
    return moved
