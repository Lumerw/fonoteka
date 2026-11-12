"""Dane startowe prototypu: konta testowe, 3 przetworzone nagrania, blog, przykładowe wpisy, lista kandydatów dla prawnika.
Uruchom: .venv/bin/python app/seed.py  (przetworzenie 3 nagrań trwa kilka minut)."""
import os, sys, json, secrets, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
import app as A
from werkzeug.security import generate_password_hash

ROOT = A.ROOT
ORIG = os.path.join(ROOT, "media", "originals")
GB = "Internet Archive – The Great 78 Project (transfer: George Blood L.P.)"

TRACKS = [
    dict(slug="twe-smutne-oczy", title="Twe smutne oczy", genre="tango",
         composer="Jakub Kagan", composer_dates="1896–1942", lyricist="Andrzej Włast", lyricist_dates="1895–1943?",
         performer="Jadwiga Czerwińska, Orkiestra Taneczna Ryszarda Franka", label="nr kat. 213, matryca OP-299-1",
         year="lata 30. (do ustalenia)", source_name=GB,
         source_url="https://archive.org/details/78_twe-smutne-oczy_jadwiga-czerwinska-orkiestra-taneczna-ryszarda-franka-j-kagan-a-w_gbia0474838a",
         desc_pl="Tango śpiewane przez Jadwigę Czerwińską z Orkiestrą Taneczną Ryszarda Franka. Muzykę napisał Jakub Kagan – pianista, aranżer i kompozytor jazzowy, autor przeboju „Złota pantera” (1929). Słowa: Andrzej Włast, najpopularniejszy tekściarz warszawskich kabaretów. Obaj zginęli w czasie wojny.\nNota biograficzna do konsultacji z muzykologiem.",
         desc_en="A tango sung by Jadwiga Czerwińska with Ryszard Frank's Dance Orchestra. Music by Jakub Kagan, pianist, arranger and jazz composer; lyrics by Andrzej Włast, the most popular lyricist of Warsaw cabarets. Both perished during the war.",
         desc_uk="Танго у виконанні Ядвіги Червінської з танцювальним оркестром Ришарда Франка. Музика Якуба Кагана – піаніста, аранжувальника і джазового композитора; слова Анджея Власта, найпопулярнішого автора текстів варшавських кабаре. Обидва загинули під час війни.",
         legal_status="preliminary",
         legal_work="Kompozytor zmarł w 1942 r. Data śmierci autora tekstu nie jest pewna; źródła podają lata 1943–1946. W każdym wariancie 70-letni okres ochrony upłynął najpóźniej z końcem 2016 r. Wstępnie: domena publiczna. Do potwierdzenia: brak innych współautorów i aranżera z prawami do opracowania.",
         legal_recording="Nagranie z lat 30. XX w.; prawa wykonawców i producenta wygasły. Do sprawdzenia: data nagrania i wytwórnia (matryca OP-299-1) oraz warunki udostępnienia kopii przez Internet Archive.",
         sources=["https://en.wikipedia.org/wiki/Jakub_Kagan", "https://polskabibliotekamuzyczna.pl/encyklopedia/wlast-andrzej/",
                  "https://archive.org/details/78_twe-smutne-oczy_jadwiga-czerwinska-orkiestra-taneczna-ryszarda-franka-j-kagan-a-w_gbia0474838a"]),
    dict(slug="szumia-jodly", title="Szumią jodły – aria Jontka z opery „Halka”", genre="aria operowa",
         composer="Stanisław Moniuszko", composer_dates="1819–1872", lyricist="Włodzimierz Wolski (libretto)", lyricist_dates="1824–1882",
         performer="Mieczysław Salecki, Orkiestra Opery Warszawskiej", label="Syrena Records, nr kat. 6001 B (wydanie Dana)",
         year="okres międzywojenny (do ustalenia)", source_name=GB,
         source_url="https://archive.org/details/78_szumia-jodly-arja-jontka-z-4go-aktu-op-halka_mieczyslaw-salecki-z-ork-opery-war_gbia0454654b",
         desc_pl="Aria Jontka z IV aktu „Halki” w wykonaniu tenora Mieczysława Saleckiego z Orkiestrą Opery Warszawskiej (część II nagrania). Jedno z najczęściej nagrywanych polskich solowych fragmentów operowych.",
         desc_en="Jontek's aria from Act IV of Moniuszko's opera Halka, sung by tenor Mieczysław Salecki with the Warsaw Opera Orchestra (part II of the recording).",
         desc_uk="Арія Йонтека з IV дії опери Монюшка «Галька» у виконанні тенора Мечислава Салецького з оркестром Варшавської опери (друга частина запису).",
         legal_status="preliminary",
         legal_work="Kompozytor zmarł w 1872 r., autor libretta w 1882 r. Utwór jest w domenie publicznej.",
         legal_recording="Nagranie Syreny z okresu międzywojennego, egzemplarz z amerykańskiego wydania Dana. Prawa pokrewne w Polsce wygasły. Do sprawdzenia: data nagrania i status w USA (wydanie Dana może być nadal chronione w USA – ewentualna blokada geograficzna).",
         sources=["https://archive.org/details/78_szumia-jodly-arja-jontka-z-4go-aktu-op-halka_mieczyslaw-salecki-z-ork-opery-war_gbia0454654b",
                  "https://pl.wikipedia.org/wiki/Halka"]),
    dict(slug="po-nieszporach", title="Po nieszporach – chór górali z opery „Halka”", genre="chór",
         composer="Stanisław Moniuszko", composer_dates="1819–1872", lyricist="Włodzimierz Wolski (libretto)", lyricist_dates="1824–1882",
         performer="Chór i Orkiestra Opery Warszawskiej", label="Syrena Records, nr kat. 6004 A (wydanie Dana)",
         year="okres międzywojenny (do ustalenia)", source_name=GB,
         source_url="https://archive.org/details/78_po-nieszporach-chr-grali-z-op-halka_chr-i-orkiestra-opery-warszawskiej-st-mo_gbia0454654a",
         desc_pl="Chór górali z „Halki” w wykonaniu Chóru i Orkiestry Opery Warszawskiej (część I nagrania). Dobry materiał do testu separacji: wiele głosów i pełna orkiestra.",
         desc_en="The highlanders' chorus from Halka performed by the Warsaw Opera Chorus and Orchestra (part I). A good separation test: many voices and a full orchestra.",
         desc_uk="Хор гуралів з «Гальки» у виконанні хору й оркестру Варшавської опери (частина I). Добрий тест сепарації: багато голосів і повний оркестр.",
         legal_status="preliminary",
         legal_work="Kompozytor zmarł w 1872 r., autor libretta w 1882 r. Utwór jest w domenie publicznej.",
         legal_recording="Jak wyżej: nagranie Syreny, egzemplarz wydania Dana; prawa pokrewne w Polsce wygasły, status w USA do sprawdzenia.",
         sources=["https://archive.org/details/78_po-nieszporach-chr-grali-z-op-halka_chr-i-orkiestra-opery-warszawskiej-st-mo_gbia0454654a"]),
]

# (tytuł, muzyka, słowa, nagranie, źródło, status wstępny, uwagi)
CANDIDATES = [
    ("Twe smutne oczy (tango)", "Jakub Kagan (1896–1942)", "Andrzej Włast (1895–1943/46)", "J. Czerwińska, Ork. R. Franka", "https://archive.org/details/78_twe-smutne-oczy_jadwiga-czerwinska-orkiestra-taneczna-ryszarda-franka-j-kagan-a-w_gbia0474838a", "prawdopodobnie DP", "W prototypie. Data śmierci Własta niepewna – w każdym wariancie DP od 2017."),
    ("Rebeka (tango, 1932)", "Zygmunt Białostocki (1897–1942)", "Andrzej Włast", "pierwsze nagranie: Zofia Terne, 1932", "https://en.wikipedia.org/wiki/Zygmunt_Bia%C5%82ostocki", "prawdopodobnie DP", "Znaleźć kopię nagrania z epoki."),
    ("Złota pantera (tango, 1929)", "Jakub Kagan (1896–1942)", "Andrzej Włast", "do odnalezienia", "https://en.wikipedia.org/wiki/Jakub_Kagan", "prawdopodobnie DP", "Znaleźć nagranie."),
    ("Szkoda twoich łez, dziewczyno (1929)", "Artur Gold (1897–1943) wg IU / „H. Gold” na etykiecie", "Andrzej Włast", "Ich Pięciu, Ork. R. Franka", "https://archive.org/details/78_szkoda-twoich-lez_ich-pieciu-orkiestra-taneczna-ryszarda-franka-h-gold-a-wlan_gbia0474835a", "WSTRZYMANY", "Sprzeczna atrybucja: jeśli Henryk Gold (zm. 1977) – chroniony do końca 2047. Nuty z epoki w Polonie mogą rozstrzygnąć."),
    ("Przy kominku", "Artur Gold (1897–1943)", "Andrzej Włast", "do odnalezienia", "", "prawdopodobnie DP", "Ustalić, czy Henryk Gold nie jest współautorem."),
    ("Daj mi całusa (tango)", "Artur Gold (1897–1943)", "Andrzej Włast", "do odnalezienia", "https://imslp.org/wiki/Daj_mi_ca%C5%82usa_(Gold,_Artur)", "prawdopodobnie DP", "Nuty w IMSLP."),
    ("Przyjdź kochanku (tango-serenada)", "Artur Gold (1897–1943)", "Andrzej Włast", "do odnalezienia", "https://imslp.org/wiki/Przyjd%C5%BA_kochanku_(Gold,_Artur)", "prawdopodobnie DP", "Nuty w IMSLP."),
    ("Melodja miłości (slow-fox)", "Artur Gold (1897–1943)", "Andrzej Włast", "do odnalezienia", "https://imslp.org/wiki/Melodja_mi%C5%82o%C5%9Bci_(Gold,_Artur)", "prawdopodobnie DP", "Nuty w IMSLP."),
    ("Tango dla mojej matki", "Zygmunt Białostocki (1897–1942)", "do ustalenia", "Ork. R. Franka, Gwido Borucki", "https://archive.org/details/78_tango-dla-mojej-matki-tango-for-my-mother_orkiestra-taneczna-ryszrda-franka-gwido_gbia3011472a", "do weryfikacji", "Ustalić autora tekstu i datę nagrania (jedna kopia datowana 1953 – poza zakresem)."),
    ("Kto usta twe całował", "Krupiński (do ustalenia)", "Andrzej Włast", "do ustalenia", "https://archive.org/details/78_kto-usta-twe-calowal_krupinski-wlast_gbia0396376b", "do weryfikacji", "Ustalić tożsamość i datę śmierci kompozytora."),
    ("Przytul, uściśnij, pocałuj", "do ustalenia (R. Nowak / W. Krupiński?)", "Andrzej Włast", "Orkiestra Braci Lewicz", "https://archive.org/details/78_przytul-uscinij-pocaluj-snuggle-close-hug-and-kiss_orkiestra-braci-lewicz-r-nowak-w_gbia0529386a", "do weryfikacji", "Ustalić role i daty śmierci współautorów."),
    ("Nie płacz baby", "Szymon Kataszek (1898–1943)", "„Jellin” – do ustalenia", "Mieczysław Fogg z orkiestrą", "https://archive.org/details/78_nie-pacz-baby-dont-cry-baby_mieczysaw-fogg-z-orkiestra-kataszek-jellin_gbia0434944a", "do weryfikacji", "Ustalić autora tekstu."),
    ("Maruszka", "J. de Leur – do ustalenia", "Andrzej Włast", "Mieczysław Fogg, Ork. Syrena Rekord", "https://archive.org/details/78_maruszka_mieczysaw-fogg-ork-syrena-rekord-j-de-leur-wast_gbia0531378a", "do weryfikacji", "Ustalić kompozytora."),
    ("Ti-Pi-Tin (wersja polska)", "María Grever (1885–1951)", "Andrzej Włast (pol.)", "Ich Pięciu, Mały zespół R. Franka", "https://archive.org/details/78_ti-pi-ton_ich-pieciu-maly-zespol-taneczny-ryszarda-franka-m-grever-a-wlast_gbia0474785a", "do analizy", "Czy polski tekst jest tłumaczeniem oryginału hiszpańskiego (Grever) czy angielskiego (R. Leveen)?"),
    ("Pamiętasz Capri (wersja polska)", "Will Grosz (1894–1939)", "Andrzej Włast (pol.)", "Ich Pięciu, Ork. R. Franka", "https://archive.org/details/78_pamietasz-capri-the-isle-of-capri_ich-pieciu-maly-zespol-taneczny-ryszarda-franka_gbia0474786a", "do analizy", "Muzyka DP; czy tekst Własta jest opracowaniem tekstu J. Kennedy'ego (zm. 1984)?"),
    ("Szumią jodły (Halka)", "Stanisław Moniuszko (1819–1872)", "Włodzimierz Wolski (1824–1882)", "Mieczysław Salecki, Ork. Opery Warszawskiej (Syrena/Dana)", "https://archive.org/details/78_szumia-jodly-arja-jontka-z-4go-aktu-op-halka_mieczyslaw-salecki-z-ork-opery-war_gbia0454654b", "DP (utwór)", "W prototypie. Data nagrania i status wydania Dana w USA."),
    ("Po nieszporach (Halka)", "Stanisław Moniuszko", "Włodzimierz Wolski", "Chór i Ork. Opery Warszawskiej (Syrena/Dana)", "https://archive.org/details/78_po-nieszporach-chr-grali-z-op-halka_chr-i-orkiestra-opery-warszawskiej-st-mo_gbia0454654a", "DP (utwór)", "W prototypie."),
    ("Gdyby rannym słonkiem (Halka)", "Stanisław Moniuszko", "Włodzimierz Wolski", "Matylda Polińska-Lewicka, Ork. Opery Warszawskiej", "https://archive.org/details/78_gdyby-rannym-slonkeim_matylda-polinska-lewicka-z-ork-opery-warszawkseij-st.-moniusz_gbia0007666a", "DP (utwór)", "Ustalić datę nagrania (czy 1918–1939)."),
    ("Kozak", "Stanisław Moniuszko", "Władysław Syrokomla (1823–1862)", "Adam Didur, 1928", "https://archive.org/details/78_kozakthecossack_217_12", "DP (utwór)", "Ustalić wytwórnię i kraj nagrania."),
    ("Gdy się Chrystus rodzi (kolęda)", "trad., opr. Feliks Nowowiejski (1877–1946)", "trad.", "Chór im. św. Cecylii, ks. B. Kopeć", "https://archive.org/details/78_gdy-sie-chrystus-rodzi_chor-im-sw-cecylii-f-nowowiejski-ks-b-kopec_gbia0278594a", "do weryfikacji", "Opracowanie DP; ustalić kraj i datę nagrania."),
    ("Rota", "Feliks Nowowiejski (1877–1946)", "Maria Konopnicka (1842–1910)", "do odnalezienia (nagranie 1918–1939)", "", "DP (utwór)", "Znaleźć nagranie z epoki."),
    ("Menuet G-dur op. 14 nr 1", "Ignacy Jan Paderewski (1860–1941)", "—", "nagrania autora z lat 20. (do odnalezienia)", "", "DP (utwór)", "Instrumentalny – separacja ograniczona; wartość historyczna."),
    ("Pieśni Mordechaja Gebirtiga (jidysz, Kraków)", "Mordechaj Gebirtig (1877–1942)", "M. Gebirtig", "szukać nagrań polskich sprzed 1939", "", "DP (utwór)", "Dostępne kopie (np. S. Belarsky 1940) są amerykańskie i spoza zakresu."),
    ("Tango Bolero", "Juan Llossas (1900–1957)", "Andrzej Włast (pol.)", "Janina Jasińska, Ork. R. Franka", "", "NIE (do 2027)", "Kompozytor zm. 1957 – domena publiczna od 1.01.2028."),
    ("Tango milonga", "Jerzy Petersburski (1895–1979)", "Andrzej Włast", "—", "", "NIE", "Przykład wykluczenia: chroniony do końca 2049."),
]

BLOG = [
    ("nagranie-wolne-piosenka-chroniona", "Nagranie wolne, piosenka chroniona? Dwa rodzaje praw", "2026-11-12",
     "Płyta z 1935 r. nie oznacza automatycznie, że wolno jej użyć. Wyjaśniamy różnicę między prawami do utworu a prawami do nagrania.",
     "<p>Każde nagranie piosenki z dwudziestolecia ma co najmniej dwie warstwy praw. Pierwsza to <strong>utwór</strong>: melodia i tekst. Chroni je prawo autorskie przez 70 lat od końca roku śmierci ostatniego z twórców. Druga to <strong>nagranie</strong>: prawa wykonawców i producenta. W przypadku płyt z lat 1918–1939 te prawa wygasły.</p><p>Dlatego „Tango milonga” Jerzego Petersburskiego (zm. 1979) pozostaje chronione do końca 2049 r., choć nagranie ma prawie sto lat. Natomiast „Twe smutne oczy” Jakuba Kagana (zm. 1942) do słów Andrzeja Własta jest – według wstępnej analizy – w domenie publicznej.</p><p>W Fonotece każdy utwór ma kartę prawną, która opisuje obie warstwy osobno i podaje źródła. Kartę potwierdza prawnik.</p>"),
    ("jak-separujemy-nagrania", "Jak rozdzielamy ścieżki w nagraniach z płyt szelakowych", "2026-11-10",
     "Nagrania z lat 30. są monofoniczne, zaszumione i wąskopasmowe. Opisujemy, co robimy i gdzie są granice tej metody.",
     "<p>Najpierw rekonstrukcja: odcinamy dudnienie poniżej 50 Hz i szum powyżej 9 kHz, gdzie płyty szelakowe i tak nie niosą muzyki, a potem stosujemy odszumianie widmowe. Następnie separacja otwartym modelem Demucs (licencja MIT). Nie trenujemy własnego modelu.</p><p>Wynik to cztery ścieżki: wokal, rytm (perkusja i bas), melodia (pozostałe instrumenty) oraz podkład bez wokalu. W nagraniach mono ścieżki przenikają się – w wokalu słychać część orkiestry. Dlatego realizator odsłuchuje każdy wynik przed publikacją, a przy słabszych nagraniach udostępniamy mniej ścieżek.</p><p>AI nie dopisuje dźwięków ani nie generuje głosu. Oryginał jest zawsze dostępny obok ścieżek.</p>"),
    ("tworcy-ktorych-nagrania-wracaja", "Kagan, Gold, Białostocki, Włast – twórcy, których piosenki wracają", "2026-11-05",
     "Wielu autorów warszawskich przebojów dwudziestolecia zginęło w czasie Zagłady. Ich utwory są dziś w domenie publicznej.",
     "<p>Jakub Kagan (1896–1942), Artur Gold (1897–1943), Zygmunt Białostocki (1897–1942) i Andrzej Włast (1895–1943?) tworzyli repertuar, który śpiewała cała przedwojenna Polska. Wszyscy zginęli w czasie wojny.</p><p>Fonoteka przywraca ich nagrania do obiegu z pełnym podpisaniem autorów i wykonawców oraz notami biograficznymi konsultowanymi z muzykologiem. Nie traktujemy ich losów jako chwytu marketingowego.</p><p class=\"muted\">Szkic tekstu – do redakcji przez muzykologa.</p>"),
]

POSTS = [
    ("projekt", "twe-smutne-oczy", "Wokal z „Twe smutne oczy” w nowym utworze", "Użyłam wyodrębnionego wokalu jako materiału do ambientowej kompozycji. W refrenie słychać orkiestrę, więc nałożyłam filtr pasmowy. Przy okazji – świetne potwierdzenie pobrania, dołączę je do zgłoszenia w dystrybutorze.", ""),
    ("poprawka", "szumia-jodly", "Data nagrania Saleckiego", "Na etykiecie jest numer Syreny 6001. Czy ktoś ma katalog Syreny, żeby ustalić rok? Mogę podesłać skan etykiety z mojego egzemplarza.", ""),
    ("zbior", None, "Kilkadziesiąt płyt Syreny po dziadku", "Mam ok. 40 płyt szelakowych, głównie tanga i fokstroty z lat 30. Chętnie udostępnię do digitalizacji – jak to zorganizować?", ""),
    ("pytanie", None, "Czy mogę użyć stemów w muzyce do gry?", "Robię niezależną grę osadzoną w Warszawie lat 30. Czy materiały ze statusem „wstępny” mogę już wykorzystać komercyjnie, czy czekać na opinię prawnika?", ""),
]


def main():
    A.init_db()
    c = A.raw_db()
    accounts = []
    for email, name, role, profile in [("admin@fonoteka.test", "Administrator", "admin", ""),
                                        ("demo@fonoteka.test", "Ola (konto testowe)", "user", "kompozytor / producent"),
                                        ("kolekcjoner@fonoteka.test", "Marek (konto testowe)", "user", "kolekcjoner")]:
        if not c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            pw = secrets.token_urlsafe(9)
            c.execute("INSERT INTO users(email,name,pw,role,profile,lang,created) VALUES(?,?,?,?,?,?,?)",
                      (email, name, generate_password_hash(pw), role, profile, "pl", A.now()))
            accounts.append((email, pw, role))
    if accounts:
        with open(os.path.join(ROOT, "data", "konta-testowe.txt"), "a") as f:
            for e, p, r in accounts:
                f.write(f"{e}\t{p}\t{r}\n")
    for tr in TRACKS:
        if c.execute("SELECT 1 FROM tracks WHERE slug=?", (tr["slug"],)).fetchone():
            continue
        tr = dict(tr)
        src = tr.pop("sources")
        cols = list(tr) + ["legal_sources", "legal_date", "status", "created"]
        c.execute(f"INSERT INTO tracks({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                  (*tr.values(), json.dumps(src, ensure_ascii=False), "2026-11-12", "draft", A.now()))
    for slug, title, date, lead, body in BLOG:
        c.execute("INSERT OR IGNORE INTO blog(slug,title,lead,body,date) VALUES(?,?,?,?,?)", (slug, title, lead, body, date))
    if not c.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]:
        c.executemany("INSERT INTO candidates(title,composer,lyricist,recording,source,status,note) VALUES(?,?,?,?,?,?,?)", CANDIDATES)
    if not c.execute("SELECT COUNT(*) FROM posts").fetchone()[0]:
        uids = [r["id"] for r in c.execute("SELECT id FROM users WHERE role='user' ORDER BY id")]
        for i, (typ, slug, title, body, link) in enumerate(POSTS):
            tid = slug and c.execute("SELECT id FROM tracks WHERE slug=?", (slug,)).fetchone()["id"]
            c.execute("INSERT INTO posts(user_id,type,track_id,title,body,link,created) VALUES(?,?,?,?,?,?,?)",
                      (uids[i % len(uids)], typ, tid, title, body, link, A.now()))
        c.execute("INSERT INTO replies(post_id,user_id,body,created) VALUES(?,?,?,?)",
                  (3, uids[0], "Napisz przez formularz współpracy – skontaktujemy Cię z realizatorem, który zrobi transfer z dokumentacją pochodzenia.", A.now()))
    c.commit()
    # przetworzenie nagrań (separacja + szkic nut), potem publikacja
    for tr in c.execute("SELECT * FROM tracks WHERE processing IS NULL").fetchall():
        p = os.path.join(ORIG, tr["slug"] + ".flac")
        if not os.path.exists(p):
            print("brak pliku", p)
            continue
        jid = A.enqueue_catalog(c, tr["id"], p)
        c.commit()
        print("przetwarzam", tr["slug"], flush=True)
        A.run_job(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
        c.execute("UPDATE tracks SET status='published' WHERE id=? AND status='review'", (tr["id"],))
        c.commit()
    write_candidates_md()
    c.close()
    print("gotowe")


def write_candidates_md():
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    L = ["# Fonoteka – kandydaci do weryfikacji prawnej (wersja wstępna)", "",
         "Stan na 12.11.2026. Lista przygotowana jako punkt wyjścia dla prawnika i muzykologa. **Nie jest opinią prawną.**", "",
         "## Kryteria", "",
         "1. **Utwór** (muzyka i tekst): domena publiczna, gdy wszyscy współtwórcy (kompozytor, autor tekstu, ewentualnie aranżer i tłumacz tekstu) zmarli najpóźniej w 1955 r. (stan na 2026) lub w 1956 r. (stan na 2027). Art. 36 pkt 1 ustawy o prawie autorskim i prawach pokrewnych.",
         "2. **Nagranie** (prawa wykonawców i producentów fonogramów): dla nagrań z lat 1918–1939 ochrona wygasła przed wejściem w życie dyrektywy 2011/77/UE; do potwierdzenia przez prawnika dla każdego nagrania (data utrwalenia i pierwszego rozpowszechnienia).",
         "3. **Kopia cyfrowa**: pochodzenie pliku i warunki udostępnienia przez archiwum (np. regulamin Internet Archive; transfery George Blood L.P.). Wierna digitalizacja nie tworzy nowych praw (art. 14 dyrektywy 2019/790, art. 33³ ustawy) – do potwierdzenia.",
         "4. **Inne kraje**: nagrania wydane w USA (np. wznowienia Dana) mogą być tam nadal chronione – ewentualna blokada geograficzna.",
         "5. **Tłumaczenia tekstów**: polski tekst do zagranicznej melodii może być opracowaniem cudzego tekstu – wymaga analizy.", "",
         "## Lista", "", "| # | Utwór | Muzyka | Słowa | Nagranie | Status wstępny | Uwagi | Źródło |", "|---|---|---|---|---|---|---|---|"]
    for i, (t, m, s, n, src, st, note) in enumerate(CANDIDATES, 1):
        L.append(f"| {i} | {t} | {m} | {s} | {n} | **{st}** | {note} | {f'[link]({src})' if src else '—'} |")
    L += ["", "## Pytania do prawnika", "",
          "1. Jak ustalać status, gdy data śmierci autora jest nieznana lub sporna (np. Andrzej Włast: 1943–1946)? Art. 36 pkt 3 (utwory anonimowe) a wiedza o tożsamości autora.",
          "2. Czy pliki z Internet Archive (Great 78 Project) możemy redystrybuować i przetwarzać, czy potrzebna jest własna digitalizacja lub zgoda archiwum?",
          "3. Czy wydania Dana (USA) wymagają blokady geograficznej dla USA?",
          "4. Wykorzystanie archiwalnych wokali w nowych utworach (koncert, EP): prawa osobiste wykonawców (art. 86 ustawy) i dobra osobiste – jak oznaczać?",
          "5. Wzór karty prawnej i regulaminu pobierania (konto, wersjonowanie karty, potwierdzenie pobrania z sumą SHA-256).",
          "6. Przeniesienie praw do transkrypcji nutowych (muzyk-transkryptor) i udostępnienie ich na CC0.",
          "7. Separator dla plików użytkowników: oświadczenie o prawach, procedura notice-and-action (DSA), usuwanie po 24 h, RODO.",
          "", "## Źródła wykorzystane do listy", "",
          "- Internet Archive, The Great 78 Project: https://archive.org/details/georgeblood",
          "- Polish Jewish Music, Indiana University (Szkoda twoich łez): https://polishjewishmusic.iu.edu/items/show/18",
          "- Polska Biblioteka Muzyczna, hasło Andrzej Włast: https://polskabibliotekamuzyczna.pl/encyklopedia/wlast-andrzej/",
          "- Wikipedia: Jakub Kagan, Zygmunt Białostocki, Artur Gold, Andrzej Włast",
          "- IMSLP, kategoria Włast, Andrzej: https://imslp.org/wiki/Category:W%C5%82ast,_Andrzej", ""]
    open(os.path.join(ROOT, "docs", "kandydaci-domena-publiczna.md"), "w").write("\n".join(L))


if __name__ == "__main__":
    main()
