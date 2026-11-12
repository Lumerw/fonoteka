"""Ponowne przetworzenie nagrań z katalogu (np. po zmianie odszumiania). Zachowuje metadane i status publikacji."""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import app as A
c = A.raw_db()
for tr in c.execute("SELECT * FROM tracks").fetchall():
    src = os.path.join(A.MEDIA, "originals", tr["slug"] + ".flac")
    if not os.path.exists(src):
        continue
    status = tr["status"]
    jid = A.enqueue_catalog(c, tr["id"], src); c.commit()
    c.execute("UPDATE tracks SET abc=NULL WHERE id=?", (tr["id"],)); c.commit()
    print("przetwarzam", tr["slug"], flush=True)
    A.run_job(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    c.execute("UPDATE tracks SET status=? WHERE id=?", (status, tr["id"])); c.commit()
    print(" ", json.loads(c.execute("SELECT processing FROM tracks WHERE id=?", (tr["id"],)).fetchone()[0]).get("denoise", {}).get("noise_reduction_db"), "dB", flush=True)
print("gotowe")
