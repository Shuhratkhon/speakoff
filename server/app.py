"""Speakoff web server: serves the website (front_end/index.html, style.css, script.js) and its JSON API.

Run (from the Speaking_Coach folder, or press Run on this file in PyCharm):
  python server/app.py                 -> open http://localhost:5000
Data (database, recordings) is in server/data/. Sign-up codes: see server/mailer.py (test mode without SMTP).
"""

import json
import re
import secrets
import sys
import time
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask, abort, g, jsonify, request, send_file, send_from_directory, session  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

from coach.i18n import LANGS, VOICES, ui  # noqa: E402
from server import credits, db, friends, oauth, mailer, plans, questions, ranked, ranks, rewards, worker  # noqa: E402

FRONT = ROOT / "front_end"
SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"]
MEDIA_EXT = {".ogg", ".oga", ".opus", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".webm", ".mp4", ".mov", ".mkv", ".3gp"}
CODE_TTL, CODE_TRIES, CODE_RESEND = 600, 5, 60          # seconds, attempts, seconds
PHOTOS = db.DATA / "photos"
PHOTO_MAX = 400 * 1024                                     # the page sends a 256x256 JPEG (~20-40 KB)

app = Flask(__name__, static_folder=None)
app.config.update(MAX_CONTENT_LENGTH=500 * 1024 * 1024, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_HTTPONLY=True, PERMANENT_SESSION_LIFETIME=timedelta(days=30))


def _secret_key():
    f = db.DATA / "secret_key"
    db.DATA.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


app.secret_key = _secret_key()


# ------------------------------------------------------------------ helpers

def err(key, status=400, **kw):
    return jsonify({"ok": False, "error": key, "params": kw}), status


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def current_user():
    uid = session.get("uid")
    return db.one("SELECT * FROM users WHERE id=?", uid) if uid else None


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        g.user = current_user()
        if g.user is None:
            return err("not_signed_in", 401)
        if not g.user["last_seen"] or time.time() - g.user["last_seen"] > 30:      # "online" for friends
            db.run("UPDATE users SET last_seen=? WHERE id=?", time.time(), g.user["id"])
        return f(*a, **kw)
    return wrapper


@app.before_request
def csrf_guard():
    """State-changing calls must come from our own page: a custom header cannot be sent by another site
    without the browser asking first (CORS), and the session cookie is SameSite=Lax."""
    if request.method == "POST" and request.path.startswith("/api/") and request.headers.get("X-SC") != "1":
        abort(403)


def user_json(u):
    return {"username": u["username"], "contact": u["contact"], "contact_type": u["contact_type"],
            "theme": u["theme"], "voice": u["voice"], "lang": u["lang"], "plan": u["plan"],
            "plan_period": u["plan_period"], "plan_renews": u["plan_renews"], "created": u["created"][:10],
            "card": ranked.card(u), "country": u["country"], "credits": u["credits"],
            "has_password": bool(u["has_password"]), "google": bool(u["google_sub"]), "apple": bool(u["apple_sub"])}


def normalise_contact(kind, value):
    value = (value or "").strip()
    if kind == "email":
        value = value.lower()
        return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", value) else None
    digits = re.sub(r"[\s\-()]", "", value)
    return digits if re.fullmatch(r"\+\d{8,15}", digits) else None


# ------------------------------------------------------------------ website files

@app.get("/")
def index():
    return send_from_directory(FRONT, "index.html")


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(FRONT, "icon.svg", mimetype="image/svg+xml")


@app.get("/<path:name>")
def static_files(name):
    if name.startswith("api/") or Path(name).suffix not in {".css", ".js", ".svg", ".png", ".ico", ".webmanifest"}:
        abort(404)
    return send_from_directory(FRONT, name)


# ------------------------------------------------------------------ languages

@app.get("/api/i18n/<lang>")
def i18n(lang):
    if lang not in LANGS:
        abort(404)
    return jsonify({"lang": lang, "langs": LANGS, "text": ui(lang)})


# ------------------------------------------------------------------ sign up / sign in

@app.post("/api/auth/start")
def auth_start():
    body = request.get_json(force=True)
    kind = body.get("method")
    if kind not in ("email", "phone"):
        abort(400)
    contact = normalise_contact(kind, body.get("contact"))
    if not contact:
        return err("err_email" if kind == "email" else "err_phone")
    if db.one("SELECT id FROM users WHERE contact=?", contact):
        return err("err_contact_taken")
    old = db.one("SELECT sent_at FROM codes WHERE contact=?", contact)
    if old and time.time() - old["sent_at"] < CODE_RESEND:
        return err("err_wait", n=int(CODE_RESEND - (time.time() - old["sent_at"])) + 1)
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.run("INSERT OR REPLACE INTO codes (contact, contact_type, code_hash, expires, attempts, sent_at) "
           "VALUES (?,?,?,?,0,?)", contact, kind, generate_password_hash(code), time.time() + CODE_TTL, time.time())
    try:
        sent = mailer.send_code(contact, kind, code)
    except Exception as e:                                     # mail server problem: fall back to test mode
        print("email failed:", e)
        sent = False
    session["signup_contact"] = contact
    session.pop("signup_verified", None)
    return jsonify({"ok": True, "contact": contact, "dev_code": None if sent else code, "resend_in": CODE_RESEND})


@app.post("/api/auth/verify")
def auth_verify():
    contact = session.get("signup_contact")
    row = db.one("SELECT * FROM codes WHERE contact=?", contact) if contact else None
    if row is None:
        return err("err_session")
    if time.time() > row["expires"] or row["attempts"] >= CODE_TRIES:
        return err("err_code_expired")
    code = re.sub(r"\D", "", request.get_json(force=True).get("code", ""))
    if not check_password_hash(row["code_hash"], code):
        db.run("UPDATE codes SET attempts = attempts + 1 WHERE contact=?", contact)
        left = CODE_TRIES - row["attempts"] - 1
        return err("err_code" if left > 0 else "err_code_expired", n=left)
    db.run("DELETE FROM codes WHERE contact=?", contact)
    session["signup_verified"] = {"contact": contact, "type": row["contact_type"], "at": time.time()}
    return jsonify({"ok": True})


@app.post("/api/auth/create")
def auth_create():
    v = session.get("signup_verified")
    if not v or time.time() - v["at"] > 3600:
        return err("err_session")
    body = request.get_json(force=True)
    username, pw, pw2 = (body.get("username") or "").strip(), body.get("password") or "", body.get("password2") or ""
    social = v.get("provider")                       # "google" / "apple": no password needed
    if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
        return err("err_username")
    if db.one("SELECT id FROM users WHERE username=?", username):
        return err("err_username_taken")
    if not social or pw or pw2:
        if len(pw) < 8:
            return err("err_password_short")
        if pw != pw2:
            return err("err_password_match")
    has_pw = bool(pw)
    if not has_pw:
        pw = secrets.token_urlsafe(32)               # unusable random password until the user sets one
    if db.one("SELECT id FROM users WHERE contact=?", v["contact"]):
        return err("err_contact_taken")
    lang = body.get("lang") if body.get("lang") in LANGS else "en"
    theme = body.get("theme") if body.get("theme") in ("dark", "light") else "dark"
    cur = db.run("INSERT INTO users (username, pw_hash, contact, contact_type, lang, theme, bonus_left, created) "
                 "VALUES (?,?,?,?,?,?,?,?)", username, generate_password_hash(pw), v["contact"], v["type"],
                 lang, theme, plans.WELCOME_BONUS, now_iso())
    db.run("UPDATE users SET has_password=? WHERE id=?", int(has_pw), cur.lastrowid)
    if social:
        db.run(f"UPDATE users SET {social}_sub=? WHERE id=?", v["sub"], cur.lastrowid)
    session.clear()
    session.permanent = True
    session["uid"] = cur.lastrowid
    return jsonify({"ok": True})


@app.get("/api/auth/providers")
def auth_providers():
    return jsonify(oauth.public_config())


@app.post("/api/auth/oauth")
def auth_oauth():
    """Google / Apple: sign in if the account is known, else continue to "choose a username"."""
    body = request.get_json(force=True)
    provider = body.get("provider")
    try:
        info = oauth.verify(provider, body.get("token"), body.get("kind", "id_token"))
    except oauth.OAuthError as e:
        return err("oauth_not_set" if str(e) == "not_configured" else "oauth_failed", name=(provider or "").title())
    except Exception as e:                                   # Google / Apple unreachable
        print("oauth failed:", e)
        return err("oauth_failed", name=(provider or "").title())
    col = f"{provider}_sub"
    u = db.one(f"SELECT * FROM users WHERE {col}=?", info["sub"])
    if u is None and info["email"] and info["email_verified"]:
        u = db.one("SELECT * FROM users WHERE contact=? AND contact_type='email'", info["email"])
        if u is not None:                                    # same verified e-mail: link this sign-in method
            db.run(f"UPDATE users SET {col}=? WHERE id=?", info["sub"], u["id"])
    if u is not None:
        session.clear()
        session.permanent = True
        session["uid"] = u["id"]
        return jsonify({"ok": True, "new": False})
    contact = info["email"] if info["email"] and info["email_verified"] else f"{provider}:{info['sub']}"
    if db.one("SELECT id FROM users WHERE contact=?", contact):
        contact = f"{provider}:{info['sub']}"
    session["signup_verified"] = {"contact": contact, "type": "email" if "@" in contact else provider,
                                  "at": time.time(), "provider": provider, "sub": info["sub"]}
    return jsonify({"ok": True, "new": True, "email": info["email"]})


@app.post("/api/auth/signin")
def auth_signin():
    body = request.get_json(force=True)
    u = db.one("SELECT * FROM users WHERE username=?", (body.get("username") or "").strip())
    if u is None or not check_password_hash(u["pw_hash"], body.get("password") or ""):
        time.sleep(0.5)                                         # slows down password guessing
        return err("err_signin")
    session.clear()
    session.permanent = True
    session["uid"] = u["id"]
    return jsonify({"ok": True})


@app.post("/api/auth/signout")
def auth_signout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    u = current_user()
    if u is None:
        return jsonify({"user": None})
    return jsonify({"user": user_json(u), "usage": plans.usage(u, db)})


# ------------------------------------------------------------------ profile

@app.post("/api/settings")
@login_required
def settings():
    body = request.get_json(force=True)
    allowed = {"theme": ("dark", "light"), "voice": ("female", "male"), "lang": tuple(LANGS)}
    for key, values in allowed.items():
        if key in body and body[key] in values:
            db.run(f"UPDATE users SET {key}=? WHERE id=?", body[key], g.user["id"])
    if "country" in body and re.fullmatch(r"[A-Z]{2}", str(body["country"] or "")):
        db.run("UPDATE users SET country=? WHERE id=?", body["country"], g.user["id"])
    return jsonify({"ok": True, "user": user_json(current_user())})


@app.post("/api/password")
@login_required
def change_password():
    body = request.get_json(force=True)
    if g.user["has_password"] and not check_password_hash(g.user["pw_hash"], body.get("current") or ""):
        return err("err_current_password")
    if len(body.get("new") or "") < 8:
        return err("err_password_short")
    if body.get("new") != body.get("new2"):
        return err("err_password_match")
    db.run("UPDATE users SET pw_hash=?, has_password=1 WHERE id=?", generate_password_hash(body["new"]), g.user["id"])
    return jsonify({"ok": True})


@app.post("/api/account/delete")
@login_required
def delete_account():
    body = request.get_json(force=True)
    if g.user["has_password"]:
        if not check_password_hash(g.user["pw_hash"], body.get("password") or ""):
            return err("err_current_password")
    elif (body.get("password") or "").strip().lower() != g.user["username"].lower():
        return err("err_type_username")
    for r in db.all_("SELECT id, audio_path, src_path FROM recordings WHERE user_id=?", g.user["id"]):
        for p in (r["audio_path"], r["src_path"]):
            if p:
                Path(p).unlink(missing_ok=True)
        for f in worker.VOICE.glob(f"{r['id']}_*.mp3"):
            f.unlink(missing_ok=True)
    db.run("DELETE FROM recordings WHERE user_id=?", g.user["id"])
    (PHOTOS / f"{g.user['id']}.jpg").unlink(missing_ok=True)
    db.run("DELETE FROM users WHERE id=?", g.user["id"])
    session.clear()
    return jsonify({"ok": True})


# ------------------------------------------------------------------ plans (test mode: no payment yet)

@app.get("/api/plans")
def plan_list():
    return jsonify({"plans": plans.public(), "test_mode": True})


@app.post("/api/plans/choose")
@login_required
def plan_choose():
    body = request.get_json(force=True)
    plan, period = body.get("plan"), body.get("period", "monthly")
    if plan not in plans.PLANS or period not in ("monthly", "yearly"):
        abort(400)
    if plan == "free":
        db.run("UPDATE users SET plan='free', plan_period=NULL, plan_renews=NULL WHERE id=?", g.user["id"])
    else:
        renews = (date.today() + timedelta(days=365 if period == "yearly" else 30)).isoformat()
        db.run("UPDATE users SET plan=?, plan_period=?, plan_renews=? WHERE id=?", plan, period, renews, g.user["id"])
    u = current_user()
    return jsonify({"ok": True, "user": user_json(u), "usage": plans.usage(u, db)})


# ------------------------------------------------------------------ home

@app.get("/api/home")
@login_required
def home():
    last = db.one("SELECT id, overall, cefr, ielts, created, status, mode FROM recordings WHERE user_id=? "
                  "AND status='done' ORDER BY created DESC LIMIT 1", g.user["id"])
    return jsonify({"daily_question": questions.for_day(), "usage": plans.usage(g.user, db),
                    "last": dict(last) if last else None, "calendar": credits.state(g.user)})


@app.post("/api/daily/claim")
@login_required
def daily_claim():
    got, st = credits.claim(g.user)
    if got is None:
        return err("already_collected")
    return jsonify({"ok": True, "reward": got, "calendar": st})


# ------------------------------------------------------------------ recordings

@app.post("/api/recordings")
@login_required
def new_recording():
    f = request.files.get("file")
    mode = request.form.get("mode", "audio")
    daily = request.form.get("daily") == "1"
    chosen = [s for s in request.form.get("sections", "").split(",") if s in SECTIONS]
    if f is None or mode not in ("audio", "video"):
        abort(400)
    if not chosen:
        return err("choose_section")
    u = g.user
    use = plans.usage(u, db)
    if daily:
        if use["daily_answered"]:
            return err("daily_done")
        chosen, max_s = SECTIONS, plans.DAILY_Q_MAX_S
    else:
        if not use["can_record"]:
            return err("no_left", 402)
        max_s = use["max_s"]
    ext = Path(f.filename or "").suffix.lower() or ".webm"
    if ext not in MEDIA_EXT:
        return err("bad_file")
    rec_id = uuid.uuid4().hex[:16]
    worker.UPLOADS.mkdir(parents=True, exist_ok=True)
    src = worker.UPLOADS / f"{rec_id}{ext}"
    f.save(src)
    from server import media
    try:
        length = media.duration(src)
    except Exception:
        src.unlink(missing_ok=True)
        return err("bad_file")
    if length < plans.MIN_SECONDS - 0.5:
        src.unlink(missing_ok=True)
        return err("too_short", len=f"{int(length // 60)}:{int(length % 60):02d}")
    used_bonus = int(not daily and u["plan"] == "free" and u["bonus_left"] > 0)
    if used_bonus:
        db.run("UPDATE users SET bonus_left = bonus_left - 1 WHERE id=?", u["id"])
    db.run("INSERT INTO recordings (id, user_id, mode, sections, question, is_daily, used_bonus, status, created, "
           "day, duration, trimmed, src_path) VALUES (?,?,?,?,?,?,?,'queued',?,?,?,?,?)",
           rec_id, u["id"], mode, ",".join(chosen), questions.for_day() if daily else None, int(daily),
           used_bonus, now_iso(), plans.today(), min(length, max_s), int(length > max_s + 0.5), str(src))
    worker.submit(rec_id)
    return jsonify({"ok": True, "id": rec_id})


def _own_recording(rec_id):
    r = db.one("SELECT * FROM recordings WHERE id=? AND user_id=?", rec_id, g.user["id"])
    if r is None:
        abort(404)
    return r


def result_view(r, lang):
    """Everything the result page shows, in the user's language."""
    from coach import feedback, grammar, level
    from coach.delivery import camera_score, camera_tips, mouth_tip
    base = {"id": r["id"], "status": r["status"], "mode": r["mode"], "created": r["created"], "question": r["question"],
            "is_daily": bool(r["is_daily"]), "trimmed": bool(r["trimmed"]), "duration": r["duration"],
            "max_s": plans.DAILY_Q_MAX_S if r["is_daily"] else plans.plan_of(g.user)["max_s"]}
    if r["status"] != "done":
        ahead = db.one("SELECT COUNT(*) n FROM recordings WHERE status IN ('queued','running') AND created < ?",
                       r["created"])["n"]
        error = r["error"] if r["status"] == "failed" else None
        speech = error.split(":")[1] if error and error.startswith("not_enough_speech:") else None
        return {**base, "ahead": ahead, "error": "not_enough_speech" if speech else ("failed_sub" if error else None),
                "params": {"n": speech} if speech else {}}
    d, chosen = json.loads(r["data"]), r["sections"].split(",")
    res = worker.summary(d, chosen)
    lv = res["level"]
    acc, per100, clean = grammar.grammar_score(d["grammar_results"], d["n_words"])
    g_total, range_score = level.grammar_total(acc, lv["grammar_range"])
    cap, _ = level.repetition_cap(lv["originality"])
    f, p, cam = d["fluency"], d["pronunciation"], (d.get("delivery") or {}).get("stats")
    keep = plans.plan_of(g.user)["keep_days"]
    return {
        **base, "chosen": chosen, "overall": res["overall"], "scores": res["sections"],
        "level": {k: lv[k] for k in ("cefr", "ielts", "ielts_parts", "toefl", "toefl_old", "too_short")},
        "fluency": {"sps": f["syllables_per_sec"], "pauses": f["pause_percent"], "mlr": f["mlr"],
                    "fillers": f["fillers"], "repairs": f["repairs"]},
        "grammar": {"accuracy": acc, "range": range_score, "per100": per100, "clean": round(clean * 100),
                    "complex": lv["grammar_range"]["complex_percent"],
                    "sentences": [{"original": s["original"], "corrected": s["corrected"],
                                   "mistakes": [{"wrong": m["wrong"], "right": m["right"],
                                                 "category": feedback.category_name(lang, m["category"])}
                                                for m in s["mistakes"]]}
                                  for s in d["grammar_results"] if s["mistakes"]]},
        "vocabulary": {"b1": lv["vocabulary"]["b1_plus"], "b2": lv["vocabulary"]["b2_plus"],
                       "variety": lv["vocabulary"]["variety"], "words": feedback.good_words(lv["vocabulary"], 12)},
        "pronunciation": {"right": round(p["right"] * 100),
                          "mistakes": [{"e": e, "h": h, "words": list(dict.fromkeys(ws))[:5], "n": len(ws)}
                                       for e, h, ws in p["mistakes"][:6]],
                          "mouth": mouth_tip(cam, lang) if cam else None},
        "camera": {"score": camera_score(cam), "tips": camera_tips(cam, lang),
                   "stats": {k: cam.get(k) for k in ("eye_contact", "smile", "head_motion", "face_visible")}}
        if cam else None,
        "repetition": {"pct": round(lv["originality"] * 100), "cap": round(cap)} if cap < 100 else None,
        "feedback": feedback.feedback_text(d, res, chosen, lang),
        "transcript": d["text"],
        "audio": bool(r["audio_path"]) and not r["audio_deleted"],
        "audio_deleted": bool(r["audio_deleted"]), "keep_days": keep,
    }


@app.get("/api/recordings/<rec_id>")
@login_required
def get_recording(rec_id):
    return jsonify(result_view(_own_recording(rec_id), g.user["lang"]))


@app.get("/api/recordings/<rec_id>/audio")
@login_required
def recording_audio(rec_id):
    r = _own_recording(rec_id)
    if not r["audio_path"] or r["audio_deleted"] or not Path(r["audio_path"]).exists():
        abort(404)
    return send_file(r["audio_path"], mimetype="audio/ogg")


@app.get("/api/recordings/<rec_id>/voice")
@login_required
def recording_voice(rec_id):
    """The AI voice is made only when the user presses Play (then kept, so replaying costs nothing)."""
    r = _own_recording(rec_id)
    if r["status"] != "done":
        abort(404)
    lang, gender = g.user["lang"], g.user["voice"]
    out = worker.VOICE / f"{rec_id}_{lang}_{gender}.mp3"
    if not out.exists():
        from coach import feedback
        d, chosen = json.loads(r["data"]), r["sections"].split(",")
        text = feedback.feedback_text(d, worker.summary(d, chosen), chosen, lang)
        try:
            feedback.speak(text, out, VOICES[lang][gender])
        except Exception as e:
            out.unlink(missing_ok=True)
            print("voice failed:", e)
            return err("voice_failed", 503)
    return send_file(out, mimetype="audio/mpeg")


# ------------------------------------------------------------------ progress (+ history)

@app.get("/api/progress")
@login_required
def progress():
    u = g.user
    full = u["plan"] != "free"
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    rows = db.all_("SELECT id, created, mode, overall, cefr, ielts, scores, status, is_daily, question, sections "
                   "FROM recordings WHERE user_id=? AND status!='failed' " + ("" if full else "AND created >= ? ") +
                   "ORDER BY created DESC", *((u["id"],) if full else (u["id"], since)))
    history = [{"id": r["id"], "created": r["created"], "mode": r["mode"], "overall": r["overall"],
                "cefr": r["cefr"], "status": r["status"], "is_daily": bool(r["is_daily"]),
                "question": r["question"]} for r in rows]
    done = [r for r in reversed(rows) if r["status"] == "done"]
    trend = [{"date": r["created"][:10], "overall": r["overall"], "scores": json.loads(r["scores"] or "{}"),
              "chosen": r["sections"].split(",")} for r in done]
    out = {"full": full, "history": history, "trend": trend,
           "count": len(done), "best": max((r["overall"] for r in done), default=None),
           "average": round(sum(r["overall"] for r in done) / len(done)) if done else None,
           "level": done[-1]["cefr"] if done else None}
    if full:
        from coach import feedback
        cats, sounds, levels = Counter(), Counter(), []
        for r in done:
            d = json.loads(db.one("SELECT data FROM recordings WHERE id=?", r["id"])["data"])
            cats.update(m["category"] for s in d["grammar_results"] for m in s["mistakes"])
            sounds.update({e: len(ws) for e, _h, ws in d["pronunciation"]["mistakes"]})
            if not levels or levels[-1]["cefr"] != r["cefr"]:
                levels.append({"date": r["created"][:10], "cefr": r["cefr"]})
        out.update({"mistakes": [{"category": feedback.category_name(u["lang"], c), "n": n} for c, n in cats.most_common(5)],
                    "sounds": [{"e": e, "n": n} for e, n in sounds.most_common(6)], "levels": levels[-8:]})
    return jsonify(out)


# ------------------------------------------------------------------ ranked 1v1 (server/ranked.py)

@app.get("/api/ranked")
@login_required
def ranked_overview():
    return jsonify(ranked.overview(g.user))


@app.get("/api/ranked/leaderboard")
@login_required
def ranked_leaderboard():
    scope = "national" if request.args.get("scope") == "national" else "global"
    return jsonify(ranked.leaderboard(g.user, scope))


@app.post("/api/ranked/queue")
@login_required
def ranked_join():
    return jsonify(ranked.join(g.user))


@app.get("/api/ranked/queue")
@login_required
def ranked_poll():
    return jsonify(ranked.poll(g.user))


@app.post("/api/ranked/leave")
@login_required
def ranked_leave():
    ranked.leave(g.user)
    return jsonify({"ok": True})


@app.get("/api/ranked/match/<match_id>")
@login_required
def ranked_match(match_id):
    v = ranked.view(g.user, match_id)
    if v is None:
        abort(404)
    return jsonify(v)


@app.post("/api/ranked/match/<match_id>/answer")
@login_required
def ranked_answer(match_id):
    f = request.files.get("file")
    if f is None:
        abort(400)
    problem = ranked.save_answer(g.user, match_id, f)
    if problem == "not_found":
        abort(404)
    if problem:
        return err(problem)
    return jsonify({"ok": True})


# ------------------------------------------------------------------ profile: photo, frame, skills, stats

def _image_kind(head):
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


@app.post("/api/profile/photo")
@login_required
def photo_upload():
    f = request.files.get("photo")
    if f is None:
        abort(400)
    data = f.read(PHOTO_MAX + 1)
    if len(data) > PHOTO_MAX or _image_kind(data[:12]) is None:
        return err("bad_photo")
    PHOTOS.mkdir(parents=True, exist_ok=True)
    (PHOTOS / f"{g.user['id']}.jpg").write_bytes(data)
    db.run("UPDATE users SET photo=? WHERE id=?", int(time.time()), g.user["id"])
    rewards.evaluate(g.user["id"])
    return jsonify({"ok": True, "user": user_json(current_user())})


@app.post("/api/profile/photo/remove")
@login_required
def photo_remove():
    (PHOTOS / f"{g.user['id']}.jpg").unlink(missing_ok=True)
    db.run("UPDATE users SET photo=0 WHERE id=?", g.user["id"])
    return jsonify({"ok": True, "user": user_json(current_user())})


@app.get("/api/photo/<username>")
@login_required
def photo_get(username):
    u = db.one("SELECT id, photo FROM users WHERE username=?", username)
    f = PHOTOS / f"{u['id']}.jpg" if u and u["photo"] else None
    if f is None or not f.exists():
        abort(404)
    kind = _image_kind(f.read_bytes()[:12])
    resp = send_file(f, mimetype={"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(kind, "image/jpeg"))
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@app.post("/api/profile/look")
@login_required
def profile_look():
    """Frame and the (at most 2) skills shown on the profile."""
    body = request.get_json(force=True)
    uid = g.user["id"]
    if "frame" in body:
        ok = {f["id"] for f in rewards.frames(uid) if f["unlocked"]}
        if body["frame"] not in ok:
            return err("locked")
        db.run("UPDATE users SET frame=? WHERE id=?", body["frame"], uid)
    if "skills" in body:
        chosen = [s for s in dict.fromkeys(body["skills"] or []) if isinstance(s, str)]
        if len(chosen) > 2 or not set(chosen) <= rewards.earned_skills(uid):
            return err("locked")
        db.run("UPDATE users SET shown_skills=? WHERE id=?", ",".join(chosen), uid)
    return jsonify({"ok": True, "user": user_json(current_user())})


@app.get("/api/profile/stats")
@login_required
def profile_stats():
    u = ranked.ensure_season(g.user)
    season = None if request.args.get("season") == "all" else u["season"]
    return jsonify({"stats": rewards.stats(u["id"], season), "season": u["season"]})


@app.get("/api/profile/awards")
@login_required
def profile_awards():
    ev = rewards.evaluate(g.user["id"])
    shown = [s for s in (current_user()["shown_skills"] or "").split(",") if s]
    return jsonify({"skills": ev["skills"], "achs": ev["achs"], "frames": rewards.frames(g.user["id"]),
                    "shown": shown, "new": ev["new"], "next_skill_in": ev["next_skill_in"], "matches": ev["matches"],
                    "block": rewards.BLOCK})


@app.get("/api/users/<username>")
@login_required
def public_profile(username):
    u = db.one("SELECT * FROM users WHERE username=?", username)
    if u is None:
        abort(404)
    u = ranked.ensure_season(u)
    n_skills = db.one("SELECT COUNT(*) n FROM skill_grants WHERE user_id=?", u["id"])["n"]
    n_achs = db.one("SELECT COUNT(*) n FROM user_awards WHERE user_id=? AND kind='ach'", u["id"])["n"]
    return jsonify({"card": ranked.card(u), "stats": rewards.stats(u["id"], u["season"]),
                    "relation": friends.relation(g.user["id"], u["id"]),
                    "skills_earned": n_skills, "achs_earned": n_achs, "me": u["id"] == g.user["id"],
                    "best_rank": ranks.rank_of(u["best_rp"])})


# ------------------------------------------------------------------ friends (server/friends.py)

@app.get("/api/friends")
@login_required
def friends_list():
    return jsonify(friends.overview(g.user["id"]))


@app.get("/api/friends/search")
@login_required
def friends_search():
    return jsonify({"users": friends.search(g.user["id"], request.args.get("q"))})


@app.post("/api/friends/<action>")
@login_required
def friends_action(action):
    body = request.get_json(force=True)
    name = body.get("username")
    if action == "request":
        problem = friends.request(g.user["id"], name)
    elif action == "respond":
        problem = friends.respond(g.user["id"], name, bool(body.get("accept")))
    elif action == "remove":
        problem = friends.remove(g.user["id"], name)
    elif action == "challenge":
        cid, problem = friends.challenge(g.user, name)
        if not problem:
            return jsonify({"ok": True, "challenge": cid})
    else:
        abort(404)
    return err(problem) if problem else jsonify({"ok": True})


@app.get("/api/challenges/pending")
@login_required
def challenges_pending():
    return jsonify({"challenges": friends.pending_challenges(g.user["id"])})


@app.get("/api/challenges/<cid>")
@login_required
def challenge_get(cid):
    st = friends.challenge_state(g.user["id"], cid)
    if st is None:
        abort(404)
    return jsonify(st)


@app.post("/api/challenges/<cid>/<action>")
@login_required
def challenge_act(cid, action):
    if action == "cancel":
        friends.cancel_challenge(g.user["id"], cid)
        return jsonify({"ok": True})
    if action not in ("accept", "decline"):
        abort(404)
    mid, problem = friends.answer_challenge(g.user, cid, action == "accept")
    return err(problem) if problem else jsonify({"ok": True, "match": mid})


# ------------------------------------------------------------------ start

def create_app(warm_up=True):
    db.init()
    worker.start(warm_up)
    return app


if __name__ == "__main__":
    create_app()
    print("Speakoff: open http://localhost:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
