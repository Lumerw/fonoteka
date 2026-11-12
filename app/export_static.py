"""Eksport statycznej wersji demonstracyjnej (PL, EN, UA) do katalogu dist/ – do wdrożenia na Cloudflare Pages."""
import os, sys, shutil, re
sys.path.insert(0, os.path.dirname(__file__))
import app as A

ROOT = A.ROOT
DIST = os.path.join(ROOT, "dist")
A.app.config["STATIC_DEMO"] = True


def pages(c):
    db = A.raw_db()
    out = ["/", "/katalog", "/separator", "/odszumianie", "/spolecznosc", "/blog", "/o-nas", "/logowanie", "/rejestracja",
           "/strona/regulamin", "/strona/prywatnosc", "/strona/dostepnosc"]
    out += [f"/utwor/{r['slug']}" for r in db.execute("SELECT slug FROM tracks WHERE status='published'")]
    out += [f"/blog/{r['slug']}" for r in db.execute("SELECT slug FROM blog")]
    out += [f"/spolecznosc/{r['id']}" for r in db.execute("SELECT id FROM posts WHERE hidden=0")]
    return out


def main():
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "app", "static"), os.path.join(DIST, "static"))
    for slug in os.listdir(os.path.join(A.MEDIA, "tracks")):
        dst = os.path.join(DIST, "media", "utwory", slug)
        os.makedirs(dst, exist_ok=True)
        for n in ("podglad.mp3", "wokal.mp3", "rytm.mp3", "melodia.mp3"):
            src = os.path.join(A.MEDIA, "tracks", slug, n)
            if os.path.exists(src):
                shutil.copy(src, dst)
    for lang in ("pl", "en", "uk"):
        prefix = "" if lang == "pl" else "/" + lang
        c = A.app.test_client()
        c.get("/?lang=" + lang)
        for path in pages(c):
            r = c.get(path, environ_base={"SCRIPT_NAME": prefix})
            if r.status_code != 200:
                print("BŁĄD", r.status_code, prefix + path)
                continue
            html = r.get_data(as_text=True)
            if prefix:
                html = html.replace(f'"{prefix}/static/', '"/static/').replace(f'"{prefix}/media/', '"/media/')
            html = re.sub(r'href="(' + re.escape(prefix) + r')?/\?lang=[a-z]+"', 'href="/"', html)
            out = os.path.join(DIST, (prefix + path).strip("/"), "index.html")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, "w").write(html)
        r = c.get("/nie-istnieje", environ_base={"SCRIPT_NAME": prefix})
        if lang == "pl":
            open(os.path.join(DIST, "404.html"), "w").write(r.get_data(as_text=True))
    open(os.path.join(DIST, "_headers"), "w").write("/*\n  X-Robots-Tag: noindex, nofollow\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n")
    open(os.path.join(DIST, "robots.txt"), "w").write("User-agent: *\nDisallow: /\n")
    n = sum(len(f) for _, _, f in os.walk(DIST))
    print("plików:", n)


if __name__ == "__main__":
    main()
