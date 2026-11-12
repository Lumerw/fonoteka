"""Ponowne wygenerowanie szkicu nut dla utworów z katalogu (po zmianie algorytmu)."""
import os, sqlite3, transcribe
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
c = sqlite3.connect(os.path.join(ROOT, "data", "fonoteka.db")); c.row_factory = sqlite3.Row
for tr in c.execute("SELECT id, slug, title, composer FROM tracks").fetchall():
    d = os.path.join(ROOT, "media", "tracks", tr["slug"])
    if os.path.exists(os.path.join(d, "wokal.flac")):
        r = transcribe.draft(os.path.join(d, "wokal.flac"), os.path.join(d, "podklad.flac"), tr["title"], tr["composer"] or "")
        if r:
            c.execute("UPDATE tracks SET abc=? WHERE id=?", (r["abc"], tr["id"])); print(tr["slug"], r["key"], r["tempo"])
c.commit()
