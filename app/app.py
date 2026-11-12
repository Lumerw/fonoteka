"""Fonoteka – prototyp. Flask + SQLite + kolejka zadań separacji (Demucs) w wątku w tle."""
import os, json, sqlite3, threading, time, uuid, hashlib, shutil, subprocess, re
from datetime import datetime, timedelta
from functools import wraps
from flask import (Flask, g, request, session, redirect, url_for, render_template, abort,
                   send_file, jsonify, flash)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from i18n import t as _t, LANGS
import denoise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "fonoteka.db")
MEDIA = os.path.join(ROOT, "media")
os.makedirs(os.path.dirname(DB), exist_ok=True)

app = Flask(__name__)
_secret = os.path.join(ROOT, "data", ".secret")
if not os.path.exists(_secret):
    open(_secret, "w").write(uuid.uuid4().hex + uuid.uuid4().hex)
app.secret_key = open(_secret).read().strip()
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE, name TEXT, pw TEXT,
  role TEXT DEFAULT 'user', profile TEXT, lang TEXT DEFAULT 'pl', created TEXT);
CREATE TABLE IF NOT EXISTS tracks(id INTEGER PRIMARY KEY, slug TEXT UNIQUE, title TEXT, genre TEXT,
  composer TEXT, composer_dates TEXT, lyricist TEXT, lyricist_dates TEXT, performer TEXT, label TEXT,
  year TEXT, duration REAL, source_name TEXT, source_url TEXT,
  desc_pl TEXT, desc_en TEXT, desc_uk TEXT, lyrics TEXT, abc TEXT,
  legal_status TEXT DEFAULT 'candidate', legal_work TEXT, legal_recording TEXT, legal_sources TEXT,
  legal_version INTEGER DEFAULT 1, legal_date TEXT, processing TEXT,
  status TEXT DEFAULT 'draft', created TEXT);
CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER, track_id INTEGER, created TEXT, PRIMARY KEY(user_id, track_id));
CREATE TABLE IF NOT EXISTS downloads(id TEXT PRIMARY KEY, user_id INTEGER, track_id INTEGER, kind TEXT,
  filename TEXT, sha256 TEXT, legal_status TEXT, legal_version INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, user_id INTEGER, kind TEXT, track_id INTEGER,
  filename TEXT, restore INTEGER DEFAULT 1, status TEXT DEFAULT 'queued', progress INTEGER DEFAULT 0,
  message TEXT, meta TEXT, created TEXT, expires TEXT);
CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, track_id INTEGER,
  title TEXT, body TEXT, link TEXT, hidden INTEGER DEFAULT 0, created TEXT);
CREATE TABLE IF NOT EXISTS replies(id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, body TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS blog(id INTEGER PRIMARY KEY, slug TEXT UNIQUE, title TEXT, lead TEXT, body TEXT, date TEXT);
CREATE TABLE IF NOT EXISTS candidates(id INTEGER PRIMARY KEY, title TEXT, composer TEXT, lyricist TEXT,
  recording TEXT, source TEXT, status TEXT, note TEXT);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def raw_db():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


@app.teardown_appcontext
def _close(e):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    c = raw_db()
    c.executescript(SCHEMA)
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN opts TEXT")
    except sqlite3.OperationalError:
        pass
    c.commit()
    c.close()


def now():
    return datetime.now().isoformat(timespec="seconds")


# ---------- język, użytkownik, szablony ----------
def lang():
    l = request.args.get("lang")
    if l in LANGS:
        session["lang"] = l
    return session.get("lang", "pl")


def user():
    if "uid" not in session:
        return None
    if "user" not in g:
        g.user = db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
    return g.user


@app.context_processor
def ctx():
    L = lang()
    return dict(t=lambda k: _t(k, L), L=L, LANGS=LANGS, me=user(), static_demo=app.config.get("STATIC_DEMO", False),
                tr_desc=lambda tr: (tr[f"desc_{L}"] or tr["desc_pl"]) if tr else "",
                fmt_date=lambda s: (s or "")[:10], fmt_dur=lambda s: f"{int(s // 60)}:{int(s % 60):02d}" if s else "")


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not user():
            flash(_t("gen.login_required", lang()))
            nxt = request.path if request.method == "GET" else "/"
            return redirect(url_for("login", next=nxt))
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        u = user()
        if not u or u["role"] != "admin":
            abort(403)
        return f(*a, **k)
    return w


@app.before_request
def csrf():
    if request.method == "POST":
        tok = session.get("csrf")
        if not tok or tok != request.form.get("csrf"):
            abort(400)


@app.context_processor
def csrf_ctx():
    if "csrf" not in session:
        session["csrf"] = uuid.uuid4().hex
    return dict(csrf=session["csrf"])


def track_dir(slug):
    return os.path.join(MEDIA, "tracks", slug)


def track_files(tr):
    d = track_dir(tr["slug"])
    return {k: os.path.exists(os.path.join(d, f)) for k, f in
            [("preview", "podglad.mp3"), ("stems", "wokal.mp3"), ("mp3", "nagranie.mp3"), ("flac", "nagranie.flac"), ("zip", "stemy.zip")]}


# ---------- strony publiczne ----------
@app.route("/")
def home():
    tracks = db().execute("SELECT * FROM tracks WHERE status='published' ORDER BY id LIMIT 6").fetchall()
    posts = db().execute("SELECT p.*, u.name FROM posts p JOIN users u ON u.id=p.user_id WHERE hidden=0 ORDER BY p.id DESC LIMIT 3").fetchall()
    blog = db().execute("SELECT * FROM blog ORDER BY date DESC LIMIT 3").fetchall()
    return render_template("home.html", tracks=tracks, posts=posts, blog=blog)


GENRES = ["tango", "fokstrot", "walc", "aria operowa", "chór", "piosenka"]


@app.route("/katalog")
def catalog():
    q = request.args.get("q", "").strip()
    genre = request.args.get("gatunek", "")
    sql, args = "SELECT * FROM tracks WHERE status='published'", []
    if q:
        like = f"%{q}%"
        sql += " AND (title LIKE ? OR composer LIKE ? OR lyricist LIKE ? OR performer LIKE ?)"
        args += [like] * 4
    if genre:
        sql += " AND genre=?"
        args.append(genre)
    tracks = db().execute(sql + " ORDER BY title", args).fetchall()
    return render_template("catalog.html", tracks=tracks, q=q, genre=genre, genres=GENRES)


@app.route("/utwor/<slug>")
def track(slug):
    tr = db().execute("SELECT * FROM tracks WHERE slug=?", (slug,)).fetchone()
    u = user()
    if not tr or (tr["status"] != "published" and not (u and u["role"] == "admin")):
        abort(404)
    saved = u and db().execute("SELECT 1 FROM favorites WHERE user_id=? AND track_id=?", (u["id"], tr["id"])).fetchone()
    posts = db().execute("SELECT p.*, u.name FROM posts p JOIN users u ON u.id=p.user_id WHERE track_id=? AND hidden=0 ORDER BY p.id DESC", (tr["id"],)).fetchall()
    proc = json.loads(tr["processing"] or "{}")
    sources = json.loads(tr["legal_sources"] or "[]")
    return render_template("track.html", tr=tr, saved=saved, posts=posts, files=track_files(tr), proc=proc, sources=sources)


@app.route("/media/utwory/<slug>/<name>")
def track_media(slug, name):
    # publiczny odsłuch: tylko lekkie podglądy MP3 128 kb/s
    if name not in {"podglad.mp3", "wokal.mp3", "rytm.mp3", "melodia.mp3", "podklad.mp3"}:
        abort(404)
    tr = db().execute("SELECT status FROM tracks WHERE slug=?", (slug,)).fetchone()
    if not tr:
        abort(404)
    p = os.path.join(track_dir(slug), name)
    if not os.path.exists(p):
        abort(404)
    return send_file(p, mimetype="audio/mpeg", conditional=True)


DL_KINDS = {"mp3": ("nagranie.mp3", "{slug}.mp3"), "flac": ("nagranie.flac", "{slug}.flac"),
            "zip": ("stemy.zip", "{slug}-stemy.zip"), "wokal": ("wokal.flac", "{slug}-wokal.flac"),
            "podklad": ("podklad.flac", "{slug}-podklad.flac"), "rytm": ("rytm.flac", "{slug}-rytm.flac"),
            "melodia": ("melodia.flac", "{slug}-melodia.flac"), "abc": (None, "{slug}.abc")}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


@app.route("/utwor/<slug>/pobierz", methods=["POST"])
@login_required
def download(slug):
    tr = db().execute("SELECT * FROM tracks WHERE slug=? AND status='published'", (slug,)).fetchone()
    kind = request.form.get("kind")
    if not tr or kind not in DL_KINDS:
        abort(404)
    if request.form.get("accept") != str(tr["legal_version"]):
        flash(_t("tr.accept", lang()) + f" {tr['legal_version']} ✓")
        return redirect(url_for("track", slug=slug) + "#pobierz")
    src, outname = DL_KINDS[kind]
    outname = outname.format(slug=slug)
    if kind == "abc":
        path = os.path.join(track_dir(slug), "zapis.abc")
        open(path, "w").write(tr["abc"] or "")
    else:
        path = os.path.join(track_dir(slug), src)
    if not os.path.exists(path):
        abort(404)
    did = uuid.uuid4().hex[:12]
    db().execute("INSERT INTO downloads VALUES(?,?,?,?,?,?,?,?,?)",
                 (did, user()["id"], tr["id"], kind, outname, sha256(path), tr["legal_status"], tr["legal_version"], now()))
    db().commit()
    return send_file(path, as_attachment=True, download_name=outname)


@app.route("/pobrania/<did>")
@login_required
def receipt(did):
    d = db().execute("""SELECT d.*, t.title, t.slug, t.composer, t.composer_dates, t.lyricist, t.lyricist_dates,
        t.performer, t.year, t.legal_work, t.legal_recording, t.source_name, t.source_url
        FROM downloads d JOIN tracks t ON t.id=d.track_id WHERE d.id=? AND d.user_id=?""", (did, user()["id"])).fetchone()
    if not d:
        abort(404)
    return render_template("receipt.html", d=d)


@app.route("/utwor/<slug>/zapisz", methods=["POST"])
@login_required
def toggle_save(slug):
    tr = db().execute("SELECT id FROM tracks WHERE slug=?", (slug,)).fetchone()
    if not tr:
        abort(404)
    uid = user()["id"]
    if db().execute("SELECT 1 FROM favorites WHERE user_id=? AND track_id=?", (uid, tr["id"])).fetchone():
        db().execute("DELETE FROM favorites WHERE user_id=? AND track_id=?", (uid, tr["id"]))
    else:
        db().execute("INSERT INTO favorites VALUES(?,?,?)", (uid, tr["id"], now()))
    db().commit()
    return redirect(request.form.get("next") or url_for("track", slug=slug))


# ---------- separator ----------
@app.route("/separator", methods=["GET", "POST"])
def separator():
    u = user()
    if request.method == "POST":
        if not u:
            return redirect(url_for("login", next="/separator"))
        f = request.files.get("audio")
        if not f or not f.filename or request.form.get("rights") != "1":
            flash(_t("sep.rights", lang()))
            return redirect(url_for("separator"))
        jid = new_user_job(u, f, "user", denoise_opts(request.form))
        return redirect(url_for("job", jid=jid))
    jobs = u and db().execute("SELECT * FROM jobs WHERE user_id=? AND kind IN ('user','denoise') ORDER BY created DESC", (u["id"],)).fetchall()
    return render_template("separator.html", jobs=jobs or [], presets=denoise.PRESETS)


def denoise_opts(form, allow_none=True):
    preset = form.get("preset", "szelak")
    if preset not in denoise.PRESETS:
        preset = None if allow_none else "szelak"
    try:
        strength = max(1, min(3, int(form.get("strength", 2))))
    except ValueError:
        strength = 2
    return {"preset": preset, "strength": strength, "hum": form.get("hum") == "1"}


def new_user_job(u, f, kind, opts):
    jid = uuid.uuid4().hex[:12]
    d = os.path.join(MEDIA, "user", jid)
    os.makedirs(d)
    name = secure_filename(f.filename) or "nagranie"
    f.save(os.path.join(d, "upload_" + name))
    db().execute("INSERT INTO jobs(id,user_id,kind,filename,restore,opts,created,expires) VALUES(?,?,?,?,?,?,?,?)",
                 (jid, u["id"], kind, name, 1 if opts.get("preset") else 0, json.dumps(opts), now(),
                  (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")))
    db().commit()
    return jid


@app.route("/odszumianie", methods=["GET", "POST"])
def denoise_page():
    u = user()
    if request.method == "POST":
        if not u:
            return redirect(url_for("login", next="/odszumianie"))
        f = request.files.get("audio")
        if not f or not f.filename or request.form.get("rights") != "1":
            flash(_t("sep.rights", lang()))
            return redirect(url_for("denoise_page"))
        jid = new_user_job(u, f, "denoise", denoise_opts(request.form, allow_none=False))
        return redirect(url_for("job", jid=jid))
    jobs = u and db().execute("SELECT * FROM jobs WHERE user_id=? AND kind='denoise' ORDER BY created DESC", (u["id"],)).fetchall()
    return render_template("denoise.html", jobs=jobs or [], presets=denoise.PRESETS)


def own_job(jid):
    j = db().execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    u = user()
    if not j or not u or (j["user_id"] != u["id"] and u["role"] != "admin"):
        abort(404)
    return j


@app.route("/separator/<jid>")
@login_required
def job(jid):
    j = own_job(jid)
    return render_template("job.html", j=j, meta=json.loads(j["meta"] or "{}"))


@app.route("/api/job/<jid>")
@login_required
def job_api(jid):
    j = own_job(jid)
    return jsonify(status=j["status"], progress=j["progress"], message=j["message"])


@app.route("/separator/<jid>/<name>")
@login_required
def job_file(jid, name):
    j = own_job(jid)
    allowed = {"przed.mp3", "po.mp3", "odszumione.flac", "odszumione.mp3", "wokal.mp3", "rytm.mp3", "melodia.mp3", "podklad.mp3", "podglad.mp3", "wokal.flac", "podklad.flac",
               "rytm.flac", "melodia.flac", "stemy.zip", "nagranie.flac", "nagranie.mp3"}
    if name not in allowed or j["status"] != "done":
        abort(404)
    p = os.path.join(MEDIA, "user", jid, name)
    if not os.path.exists(p):
        abort(404)
    return send_file(p, as_attachment=not name.endswith(".mp3") or request.args.get("dl") == "1", conditional=True)


# ---------- społeczność ----------
POST_TYPES = ["projekt", "pytanie", "poprawka", "zbior"]


@app.route("/spolecznosc", methods=["GET", "POST"])
def community():
    if request.method == "POST":
        u = user()
        if not u:
            return redirect(url_for("login", next="/spolecznosc"))
        f = request.form
        title, body = f.get("title", "").strip()[:200], f.get("body", "").strip()[:5000]
        typ = f.get("type") if f.get("type") in POST_TYPES else "pytanie"
        link = f.get("link", "").strip()[:500]
        if link and not re.match(r"^https?://", link):
            link = ""
        tid = f.get("track_id") or None
        if title and body:
            db().execute("INSERT INTO posts(user_id,type,track_id,title,body,link,created) VALUES(?,?,?,?,?,?,?)",
                         (u["id"], typ, tid, title, body, link, now()))
            db().commit()
        return redirect(url_for("community"))
    typ = request.args.get("typ", "")
    sql = "SELECT p.*, u.name, t.title AS ttitle, t.slug AS tslug, (SELECT COUNT(*) FROM replies r WHERE r.post_id=p.id) AS nrep FROM posts p JOIN users u ON u.id=p.user_id LEFT JOIN tracks t ON t.id=p.track_id WHERE hidden=0"
    args = []
    if typ in POST_TYPES:
        sql += " AND p.type=?"
        args.append(typ)
    posts = db().execute(sql + " ORDER BY p.id DESC", args).fetchall()
    tracks = db().execute("SELECT id, title FROM tracks WHERE status='published' ORDER BY title").fetchall()
    pre = {"type": request.args.get("nowy", ""), "track": request.args.get("utwor", "")}
    return render_template("community.html", posts=posts, typ=typ, types=POST_TYPES, tracks=tracks, pre=pre)


@app.route("/spolecznosc/<int:pid>", methods=["GET", "POST"])
def post(pid):
    p = db().execute("SELECT p.*, u.name, t.title AS ttitle, t.slug AS tslug FROM posts p JOIN users u ON u.id=p.user_id LEFT JOIN tracks t ON t.id=p.track_id WHERE p.id=? AND hidden=0", (pid,)).fetchone()
    if not p:
        abort(404)
    if request.method == "POST":
        if not user():
            return redirect(url_for("login", next=request.path))
        body = request.form.get("body", "").strip()[:3000]
        if body:
            db().execute("INSERT INTO replies(post_id,user_id,body,created) VALUES(?,?,?,?)", (pid, user()["id"], body, now()))
            db().commit()
        return redirect(url_for("post", pid=pid))
    reps = db().execute("SELECT r.*, u.name FROM replies r JOIN users u ON u.id=r.user_id WHERE post_id=? ORDER BY r.id", (pid,)).fetchall()
    return render_template("post.html", p=p, reps=reps)


@app.route("/spolecznosc/<int:pid>/ukryj", methods=["POST"])
@admin_required
def hide_post(pid):
    db().execute("UPDATE posts SET hidden=1 WHERE id=?", (pid,))
    db().commit()
    return redirect(url_for("community"))


# ---------- blog, o nas, strony prawne ----------
@app.route("/blog")
def blog():
    return render_template("blog.html", posts=db().execute("SELECT * FROM blog ORDER BY date DESC").fetchall())


@app.route("/blog/<slug>")
def blog_post(slug):
    b = db().execute("SELECT * FROM blog WHERE slug=?", (slug,)).fetchone()
    if not b:
        abort(404)
    return render_template("blog_post.html", b=b)


@app.route("/o-nas")
def about():
    return render_template("about.html")


@app.route("/strona/<name>")
def page(name):
    if name not in {"regulamin", "prywatnosc", "dostepnosc"}:
        abort(404)
    return render_template("page.html", name=name)


# ---------- konto ----------
@app.route("/logowanie", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?", (request.form.get("email", "").strip().lower(),)).fetchone()
        if u and check_password_hash(u["pw"], request.form.get("password", "")):
            session.clear()
            session["uid"] = u["id"]
            session["lang"] = u["lang"] or "pl"
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("panel"))
        flash(_t("acc.bad", lang()))
    return render_template("login.html")


@app.route("/rejestracja", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        email = f.get("email", "").strip().lower()
        if len(f.get("password", "")) < 8:
            flash(_t("acc.short", lang()))
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or f.get("terms") != "1":
            flash(_t("acc.terms", lang()))
        elif db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash(_t("acc.exists", lang()))
        else:
            cur = db().execute("INSERT INTO users(email,name,pw,profile,lang,created) VALUES(?,?,?,?,?,?)",
                               (email, f.get("name", "").strip()[:80] or email.split("@")[0],
                                generate_password_hash(f["password"]), f.get("profile", "")[:40], lang(), now()))
            db().commit()
            session["uid"] = cur.lastrowid
            return redirect(url_for("panel"))
    return render_template("register.html")


@app.route("/wyloguj", methods=["POST"])
def logout():
    l = session.get("lang", "pl")
    session.clear()
    session["lang"] = l
    return redirect(url_for("home"))


@app.route("/panel", methods=["GET", "POST"])
@login_required
def panel():
    u = user()
    if request.method == "POST":
        f = request.form
        l = f.get("lang") if f.get("lang") in LANGS else u["lang"]
        db().execute("UPDATE users SET name=?, profile=?, lang=? WHERE id=?",
                     (f.get("name", u["name"]).strip()[:80], f.get("profile", "")[:40], l, u["id"]))
        db().commit()
        session["lang"] = l
        return redirect(url_for("panel") + "#ustawienia")
    uid = u["id"]
    lib = db().execute("SELECT t.* FROM favorites f JOIN tracks t ON t.id=f.track_id WHERE f.user_id=? ORDER BY f.created DESC", (uid,)).fetchall()
    dls = db().execute("SELECT d.*, t.title, t.slug FROM downloads d JOIN tracks t ON t.id=d.track_id WHERE d.user_id=? ORDER BY d.created DESC LIMIT 50", (uid,)).fetchall()
    jobs = db().execute("SELECT * FROM jobs WHERE user_id=? AND kind IN ('user','denoise') ORDER BY created DESC", (uid,)).fetchall()
    posts = db().execute("SELECT p.*, (SELECT COUNT(*) FROM replies r WHERE r.post_id=p.id) AS nrep FROM posts p WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    return render_template("panel.html", lib=lib, dls=dls, jobs=jobs, posts=posts)


@app.route("/panel/eksport")
@login_required
def export_data():
    uid = user()["id"]
    q = lambda s: [dict(r) for r in db().execute(s, (uid,)).fetchall()]
    data = {"konto": {k: user()[k] for k in ("email", "name", "profile", "lang", "created")},
            "biblioteka": q("SELECT t.slug, f.created FROM favorites f JOIN tracks t ON t.id=f.track_id WHERE f.user_id=?"),
            "pobrania": q("SELECT * FROM downloads WHERE user_id=?"),
            "wpisy": q("SELECT * FROM posts WHERE user_id=?"), "odpowiedzi": q("SELECT * FROM replies WHERE user_id=?")}
    r = jsonify(data)
    r.headers["Content-Disposition"] = "attachment; filename=fonoteka-moje-dane.json"
    return r


@app.route("/panel/usun", methods=["POST"])
@login_required
def delete_account():
    uid = user()["id"]
    for j in db().execute("SELECT id FROM jobs WHERE user_id=?", (uid,)).fetchall():
        shutil.rmtree(os.path.join(MEDIA, "user", j["id"]), ignore_errors=True)
    for s in ("DELETE FROM favorites WHERE user_id=?", "DELETE FROM downloads WHERE user_id=?", "DELETE FROM jobs WHERE user_id=?",
              "DELETE FROM replies WHERE user_id=?", "DELETE FROM replies WHERE post_id IN (SELECT id FROM posts WHERE user_id=?)",
              "DELETE FROM posts WHERE user_id=?", "DELETE FROM users WHERE id=?"):
        db().execute(s, (uid,))
    db().commit()
    session.clear()
    return redirect(url_for("home"))


# ---------- administracja ----------
@app.route("/admin")
@admin_required
def admin():
    tracks = db().execute("SELECT * FROM tracks ORDER BY id DESC").fetchall()
    jobs = db().execute("SELECT j.*, u.email FROM jobs j LEFT JOIN users u ON u.id=j.user_id ORDER BY created DESC LIMIT 30").fetchall()
    cands = db().execute("SELECT * FROM candidates ORDER BY id").fetchall()
    stats = {k: db().execute(s).fetchone()[0] for k, s in [("users", "SELECT COUNT(*) FROM users"), ("downloads", "SELECT COUNT(*) FROM downloads"), ("jobs", "SELECT COUNT(*) FROM jobs")]}
    return render_template("admin.html", tracks=tracks, jobs=jobs, cands=cands, stats=stats)


TRACK_FIELDS = ["title", "genre", "composer", "composer_dates", "lyricist", "lyricist_dates", "performer", "label", "year",
                "source_name", "source_url", "desc_pl", "desc_en", "desc_uk", "lyrics", "abc", "legal_status", "legal_work", "legal_recording"]


@app.route("/admin/utwor/<int:tid>", methods=["GET", "POST"])
@app.route("/admin/utwor/nowy", methods=["GET", "POST"], defaults={"tid": None})
@admin_required
def admin_track(tid):
    tr = tid and db().execute("SELECT * FROM tracks WHERE id=?", (tid,)).fetchone()
    if request.method == "POST":
        f = request.form
        vals = {k: f.get(k, "").strip() for k in TRACK_FIELDS}
        sources = [s.strip() for s in f.get("legal_sources", "").splitlines() if s.strip()]
        if not tr:
            slug = re.sub(r"[^a-z0-9]+", "-", vals["title"].lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))).strip("-") or uuid.uuid4().hex[:6]
            if db().execute("SELECT 1 FROM tracks WHERE slug=?", (slug,)).fetchone():
                slug += "-" + uuid.uuid4().hex[:4]
            cur = db().execute(f"INSERT INTO tracks(slug,{','.join(TRACK_FIELDS)},legal_sources,legal_date,status,created) VALUES(?{',?' * len(TRACK_FIELDS)},?,?,?,?)",
                               (slug, *vals.values(), json.dumps(sources, ensure_ascii=False), now()[:10], "draft", now()))
            tid = cur.lastrowid
        else:
            legal_changed = any((tr[k] or "") != vals[k] for k in ("legal_status", "legal_work", "legal_recording")) or json.loads(tr["legal_sources"] or "[]") != sources
            ver = tr["legal_version"] + (1 if legal_changed else 0)
            db().execute(f"UPDATE tracks SET {','.join(k + '=?' for k in TRACK_FIELDS)}, legal_sources=?, legal_version=?, legal_date=? WHERE id=?",
                         (*vals.values(), json.dumps(sources, ensure_ascii=False), ver, now()[:10] if legal_changed else tr["legal_date"], tid))
            if f.get("status") in ("draft", "review", "published"):
                db().execute("UPDATE tracks SET status=? WHERE id=?", (f["status"], tid))
        audio = request.files.get("audio")
        if audio and audio.filename:
            slug = db().execute("SELECT slug FROM tracks WHERE id=?", (tid,)).fetchone()["slug"]
            os.makedirs(os.path.join(MEDIA, "originals"), exist_ok=True)
            p = os.path.join(MEDIA, "originals", slug + os.path.splitext(secure_filename(audio.filename))[1])
            audio.save(p)
            enqueue_catalog(db(), tid, p)
        db().commit()
        return redirect(url_for("admin_track", tid=tid))
    return render_template("admin_track.html", tr=tr, genres=GENRES,
                           sources="\n".join(json.loads(tr["legal_sources"] or "[]")) if tr else "")


def enqueue_catalog(c, tid, path):
    jid = uuid.uuid4().hex[:12]
    c.execute("INSERT INTO jobs(id,user_id,kind,track_id,filename,restore,created) VALUES(?,?,?,?,?,?,?)",
              (jid, None, "catalog", tid, path, 1, now()))
    c.execute("UPDATE tracks SET status='processing' WHERE id=?", (tid,))
    return jid


# ---------- kolejka zadań ----------
def _duration(p):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                             capture_output=True, text=True, check=True).stdout
        return float(out.strip())
    except Exception:
        return None


def run_job(j):
    import separator, transcribe
    c = raw_db()

    def prog(p, m):
        c.execute("UPDATE jobs SET progress=?, message=? WHERE id=?", (p, m, j["id"]))
        c.commit()

    try:
        c.execute("UPDATE jobs SET status='running' WHERE id=?", (j["id"],))
        c.commit()
        opts = json.loads(j["opts"] or "{}") if "opts" in j.keys() else {}
        if j["kind"] in ("user", "denoise"):
            d = os.path.join(MEDIA, "user", j["id"])
            src = os.path.join(d, "upload_" + j["filename"])
            dur = _duration(src)
            if dur is None:
                raise ValueError("Nie udało się odczytać pliku audio.")
            if dur > 300:  # limit 5 minut: przycinamy
                cut = os.path.join(d, "cut.wav")
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-t", "300", cut], check=True)
                os.remove(src)
                src = cut
            if j["kind"] == "denoise":
                meta = denoise.process_job(src, d, opts.get("preset", "szelak"), opts.get("strength", 2), opts.get("hum", False), prog)
                os.remove(os.path.join(d, "odszumione.wav"))
            else:
                files, meta = separator.separate(src, d, restore=opts.get("preset", "szelak" if j["restore"] else None),
                                                 strength=opts.get("strength", 2), hum=opts.get("hum", False), progress=prog)
            os.remove(src)
        else:
            tr = c.execute("SELECT * FROM tracks WHERE id=?", (j["track_id"],)).fetchone()
            d = track_dir(tr["slug"])
            files, meta = separator.separate(j["filename"], d, restore=opts.get("preset", "szelak"), strength=opts.get("strength", 2),
                                             hum=opts.get("hum", False), progress=lambda p, m: prog(int(p * 0.8), m))
            prog(85, "Szkic zapisu nutowego")
            abc = None
            try:
                r = transcribe.draft(files["wokal"], files["podklad"], tr["title"], tr["composer"] or "")
                abc = r and r["abc"]
                meta["notation"] = r and {k: r[k] for k in ("key", "tempo", "bars")}
            except Exception as e:  # szkic jest opcjonalny
                meta["notation_error"] = str(e)
            dur = _duration(files["mp3"])
            c.execute("UPDATE tracks SET processing=?, duration=?, abc=COALESCE(NULLIF(abc,''),?), status='review' WHERE id=?",
                      (json.dumps(meta), dur, abc, tr["id"]))
        c.execute("UPDATE jobs SET status='done', progress=100, message='Gotowe', meta=? WHERE id=?", (json.dumps(meta), j["id"]))
        c.commit()
    except Exception as e:
        c.execute("UPDATE jobs SET status='error', message=? WHERE id=?", (str(e)[:300], j["id"]))
        c.commit()
    finally:
        c.close()


def worker():
    while True:
        try:
            c = raw_db()
            j = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            # sprzątanie: separacje użytkowników starsze niż 24 h
            for old in c.execute("SELECT id FROM jobs WHERE kind IN ('user','denoise') AND expires < ? AND status!='expired'", (now(),)).fetchall():
                shutil.rmtree(os.path.join(MEDIA, "user", old["id"]), ignore_errors=True)
                c.execute("UPDATE jobs SET status='expired' WHERE id=?", (old["id"],))
            c.commit()
            c.close()
            if j:
                run_job(j)
            else:
                time.sleep(2)
        except Exception as e:
            print("worker:", e)
            time.sleep(5)


@app.errorhandler(404)
def e404(e):
    return render_template("error.html", code=404), 404


@app.errorhandler(403)
def e403(e):
    return render_template("error.html", code=403), 403


@app.errorhandler(413)
def e413(e):
    return render_template("error.html", code=413), 413


init_db()
if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5055)), debug=False, threaded=True)
