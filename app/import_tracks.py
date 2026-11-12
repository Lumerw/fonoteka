"""Import kolejnych nagrań z Internet Archive (Great 78 Project i in.) do katalogu Fonoteki.

Uruchom:  .venv/bin/python app/import_tracks.py                # dodaje brakujące, przetwarza nieprzetworzone
          .venv/bin/python app/import_tracks.py --no-process   # tylko metadane, karta prawna, kandydaci
          .venv/bin/python app/import_tracks.py --only kozak-didur,maruszka --reprocess

Skrypt można uruchamiać wielokrotnie: aktualizuje metadane istniejących wierszy (bez zmiany wersji karty, gdy
treść prawna się nie zmieniła), pobiera brakujące pliki FLAC do media/originals/<slug>.flac i przetwarza tylko
utwory bez wyniku (processing IS NULL) – chyba że podano --reprocess.

Status publikacji: `publish=True` tylko wtedy, gdy wszyscy twórcy na pewno zmarli najpóźniej w 1955 r.
i nagranie pochodzi z lat 1918–1939. Pozostałe trafiają do statusu `review` (widoczne tylko dla admina).
Karty prawne to wstępna analiza, nie opinia prawna.
"""
import os, sys, json, argparse, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
import app as A

ROOT = A.ROOT
ORIG = os.path.join(ROOT, "media", "originals")
GB = "Internet Archive – The Great 78 Project (transfer: George Blood L.P.)"
IA78 = "Internet Archive – kolekcja 78rpm"
TODAY = "2026-11-12"
NOTE = "Wstępna analiza (nie jest opinią prawną) – do potwierdzenia przez prawnika."

SM = "https://staremelodie.pl/piosenka/"
HALKA_DANA = ("Nagranie „Halki” wytwórni Syrena-Electro z lat 1929–1930 (wg Wikipedii: partię Halki Polińska-Lewicka nagrała "
              "dla Syreny w 1929 r.; komplet wydano w 1932 r.). Egzemplarz z Internet Archive to amerykańskie wznowienie "
              "wytwórni Dana (Nowy Jork), która w 1948 r. przejęła matryce Syreny. Prawa wykonawców i producenta w Polsce wygasły. "
              "Do sprawdzenia: status wznowienia Dana w USA (ewentualna blokada geograficzna) – jak przy „Szumią jodły”.")
HALKA_WORK = "Muzyka: Stanisław Moniuszko (zm. 1872). Libretto: Włodzimierz Wolski (zm. 1882). Utwór w domenie publicznej."
DIDUR_REC = ("Nagranie amerykańskie: Brunswick 60049, 1928 (wg katalogu Stanford; miejsce nagrania – Nowy Jork – niepotwierdzone "
             "źródłem pierwotnym). W Polsce i UE prawa do nagrania wygasły. W USA nagrania opublikowane w 1928 r. są chronione "
             "do 31.12.2028 (Music Modernization Act) – do decyzji prawnika: blokada geograficzna dla USA do końca 2028 r.")
MOSS_REC = ("Nagranie Syrena-Electro z 1931 r. (nr kat. 3653, wg staremelodie.pl; numery matryc w źródłach niespójne: 21751/21746/21650). "
            "Egzemplarz z Internet Archive to amerykańskie wznowienie White Eagle z adnotacją „Recorded in Poland”. "
            "Prawa wykonawców i producenta w Polsce wygasły; status wznowienia w USA do sprawdzenia.")
MOSS_ARR = ("BRAKUJE: autor opracowania (aranżacji na baryton, chór i orkiestrę) nie jest podany na etykiecie ani w znanych źródłach. "
            "Jeśli opracował je dyrygent chóru Wacław Lachman (zm. 16.10.1963) – opracowanie chronione do końca 2033 r.; "
            "jeśli Bronisław Szulc (zm. 17.04.1955) – w domenie publicznej od 1.01.2026. Do czasu ustalenia: status „kandydat”, bez publikacji.")
BIEL_REC = ("Nagranie akustyczne Odeon 11056 (seria amerykańska Okeh-Odeon), 1922 wg opisu Internet Archive, z adnotacją „Recorded in Poland”. "
            "Seria Okeh-Odeon 11000 obejmowała zarówno nagrania amerykańskie, jak i importowane matryce europejskie – miejsce nagrania "
            "niepotwierdzone. Tożsamości śpiewaka (Paweł Bielański) nie udało się ustalić. Prawa do nagrania wygasły w Polsce; "
            "w USA nagrania opublikowane przed 1923 r. są w domenie publicznej od 1.01.2022.")

# Klucze: slug, ia (identyfikator Internet Archive), ia_file (plik FLAC), publish (True = status 'published'), sources.
TRACKS = [
    dict(slug="kozak-didur", ia="78_kozakthecossack_217_12", ia_file="Kozak(The Cossack) - Adamo Didur - Stanislav Moniuszko.flac",
         publish=True, source_name=IA78 + " (78-opera)",
         title="Kozak – pieśń Stanisława Moniuszki", genre="piosenka",
         composer="Stanisław Moniuszko", composer_dates="1819–1872",
         lyricist="Jan Czeczot (atrybucja; dawniej podawano Władysława Syrokomlę)", lyricist_dates="1796–1847",
         performer="Adam Didur (bas), z orkiestrą", label="Brunswick 60049-B (matryca wg IA: 476)", year="1928 (USA)",
         desc_pl="Pieśń „Kozak” ze „Śpiewnika domowego” Moniuszki w wykonaniu Adama Didura (1874–1946), jednego z najsłynniejszych basów swojej epoki, przez ponad dwadzieścia lat solisty Metropolitan Opera w Nowym Jorku. Nagranie ukazało się w polskiej serii amerykańskiej wytwórni Brunswick.\nNota biograficzna do konsultacji z muzykologiem.",
         desc_en="Moniuszko's song “Kozak” (The Cossack) from his Songbook for Home Use, sung by Adam Didur (1874–1946), one of the great basses of his era and for over twenty years a soloist of the Metropolitan Opera in New York. Issued in Brunswick's Polish series.",
         desc_uk="Пісня Монюшка «Козак» зі «Співаника домашнього» у виконанні Адама Дідура (1874–1946), одного з найславетніших басів своєї епохи, понад двадцять років соліста Метрополітен-опери в Нью-Йорку. Запис вийшов у польській серії американської фірми Brunswick.",
         legal_status="preliminary",
         legal_work="Muzyka: Stanisław Moniuszko (zm. 1872). Słowa: według POLMIC i katalogu Biblioteki Jagiellońskiej Jan Czeczot (zm. 1847); POLMIC oznacza atrybucję znakiem zapytania, a dawniejsze opisy (także nasza lista kandydatów) podawały Władysława Syrokomlę (zm. 1862). W każdym wariancie autor tekstu zmarł w XIX w. Utwór w domenie publicznej.",
         legal_recording=DIDUR_REC,
         sources=["https://polmic.pl/pl/encyklopedia/osobowe/m/moniuszko-stanislaw", "https://pl.wikipedia.org/wiki/Jan_Czeczot",
                  "https://pl.wikipedia.org/wiki/Adam_Didur",
                  "https://searchworks.stanford.edu/catalog?q=%22Didur%2C+Adam%2C+1874-1946%22&search_field=search_author"]),
    dict(slug="piesn-chorazego", ia="78_songoftheemblem-bearer_217_11", ia_file="Songoftheemblem-bearer - Adamo Didur - Stanislav Moniuszko.flac",
         publish=True, source_name=IA78 + " (78-opera)",
         title="Pieśń Chorążego z opery „Hrabina”", genre="aria operowa",
         composer="Stanisław Moniuszko", composer_dates="1819–1872",
         lyricist="Włodzimierz Wolski (libretto)", lyricist_dates="1824–1882",
         performer="Adam Didur (bas), z orkiestrą", label="Brunswick 60049-A (matryca wg IA: 475)", year="1928 (USA)",
         desc_pl="Fragment opery „Hrabina” (1860) Moniuszki do libretta Włodzimierza Wolskiego w wykonaniu Adama Didura – druga strona płyty z pieśnią „Kozak”. Polski tytuł odtworzono z angielskiego opisu archiwum („Song of the emblem-bearer”); do sprawdzenia z etykietą.\nNota do konsultacji z muzykologiem.",
         desc_en="An excerpt from Moniuszko's opera The Countess (1860, libretto by Włodzimierz Wolski) sung by Adam Didur – the flip side of “Kozak”. The Polish title was reconstructed from the archive's English description and should be checked against the label.",
         desc_uk="Фрагмент опери Монюшка «Графиня» (1860, лібрето Влодзімежа Вольського) у виконанні Адама Дідура – зворотний бік платівки з піснею «Козак». Польську назву відновлено з англійського опису архіву; її слід звірити з етикеткою.",
         legal_status="preliminary",
         legal_work="Muzyka: Stanisław Moniuszko (zm. 1872). Libretto: Włodzimierz Wolski (zm. 1882). Utwór w domenie publicznej.",
         legal_recording=DIDUR_REC,
         sources=["https://pl.wikipedia.org/wiki/Hrabina_(opera)", "https://pl.wikipedia.org/wiki/Adam_Didur"]),
    dict(slug="gdyby-rannym-slonkiem", ia="78_gdyby-rannym-slonkeim_matylda-polinska-lewicka-z-ork-opery-warszawkseij-st.-moniusz_gbia0007666a",
         ia_file="Gdyby Rannym Slonkeim - Matylda Polinska-Lewicka z ork Opery Warszawkseij.flac", publish=True,
         title="Gdyby rannym słonkiem – recytatyw i aria Halki (akt II)", genre="aria operowa",
         composer="Stanisław Moniuszko", composer_dates="1819–1872", lyricist="Włodzimierz Wolski (libretto)", lyricist_dates="1824–1882",
         performer="Matylda Polińska-Lewicka (sopran), Orkiestra Opery Warszawskiej",
         label="Syrena-Electro; egzemplarz: Dana 6003-B (wznowienie z matryc Syreny)", year="1929–1930",
         desc_pl="Najsłynniejsza aria Halki w wykonaniu Matyldy Polińskiej-Lewickiej (1881–1968), solistki Opery Warszawskiej i wybitnej odtwórczyni tej partii. Pochodzi z nagrania „Halki” zrealizowanego przez Syrenę w latach 1929–1930 – jednego z pierwszych tak obszernych nagrań polskiej opery.\nNota biograficzna do konsultacji z muzykologiem.",
         desc_en="Halka's most famous aria sung by Matylda Polińska-Lewicka (1881–1968), a Warsaw Opera soloist renowned in the role. From Syrena's 1929–30 recording of Halka, one of the first extensive recordings of a Polish opera.",
         desc_uk="Найвідоміша арія Гальки у виконанні Матильди Поліньської-Левицької (1881–1968), солістки Варшавської опери, видатної виконавиці цієї партії. Із запису «Гальки», зробленого фірмою «Сирена» у 1929–1930 роках.",
         legal_status="preliminary", legal_work=HALKA_WORK, legal_recording=HALKA_DANA,
         sources=["https://pl.wikipedia.org/wiki/Matylda_Polińska-Lewicka", "https://en.wikipedia.org/wiki/Syrena_Rekord",
                  "https://en.wikipedia.org/wiki/Dana_Records"]),
    dict(slug="o-moj-malenki", ia="78_o-moj-malenki_matylda-polinska-lewicka-z-ork-opery-warszawkseij-st.-moniuszko_gbia0007666b",
         ia_file="O Moj Malenki - Matylda Polinska-Lewicka z ork Opery Warszawkseij.flac", publish=True,
         title="O mój maleńki – śpiew Halki z opery „Halka”", genre="aria operowa",
         composer="Stanisław Moniuszko", composer_dates="1819–1872", lyricist="Włodzimierz Wolski (libretto)", lyricist_dates="1824–1882",
         performer="Matylda Polińska-Lewicka (sopran), Orkiestra Opery Warszawskiej",
         label="Syrena-Electro; egzemplarz: Dana 6002-B (wznowienie z matryc Syreny)", year="1929–1930",
         desc_pl="Kołysankowy śpiew Halki „O mój maleńki” w wykonaniu Matyldy Polińskiej-Lewickiej z Orkiestrą Opery Warszawskiej, z nagrania „Halki” Syreny z lat 1929–1930.",
         desc_en="Halka's lullaby-like song “O mój maleńki” (O my little one) sung by Matylda Polińska-Lewicka with the Warsaw Opera Orchestra, from Syrena's 1929–30 recording of Halka.",
         desc_uk="Колисковий спів Гальки «О мій маленький» у виконанні Матильди Поліньської-Левицької з оркестром Варшавської опери, із запису «Гальки» фірми «Сирена» 1929–1930 років.",
         legal_status="preliminary", legal_work=HALKA_WORK, legal_recording=HALKA_DANA,
         sources=["https://pl.wikipedia.org/wiki/Matylda_Polińska-Lewicka", "https://en.wikipedia.org/wiki/Syrena_Rekord"]),
    dict(slug="niechaj-bedzie-pochwalony", ia="78_niechaj-bedzie-pochwalony_matylda-polinska-lewicka-w.-bregy--opery-warszawskiej_gbia0007562a",
         ia_file="Niechaj Bedzie Pochwalony - Matylda Polinska Lewicka.flac", publish=True,
         title="Niechaj będzie pochwalony – duet z III aktu opery „Halka”", genre="aria operowa",
         composer="Stanisław Moniuszko", composer_dates="1819–1872", lyricist="Włodzimierz Wolski (libretto)", lyricist_dates="1824–1882",
         performer="Matylda Polińska-Lewicka (sopran), Wiktor Brégy (tenor), Orkiestra Opery Warszawskiej",
         label="Syrena-Electro (na etykiecie także nr 20863 – prawdopodobnie matryca); egzemplarz: Dana 6005-A", year="1929–1930",
         desc_pl="Duet Halki i Jontka z III aktu w wykonaniu Matyldy Polińskiej-Lewickiej i Wiktora Brégy’ego (1903–1976) – tenora, później reżysera operowego. Z nagrania „Halki” Syreny z lat 1929–1930.\nNota biograficzna do konsultacji z muzykologiem.",
         desc_en="The Act III duet of Halka and Jontek sung by Matylda Polińska-Lewicka and Wiktor Brégy (1903–1976), tenor and later opera director. From Syrena's 1929–30 recording of Halka.",
         desc_uk="Дует Гальки та Йонтека з III дії у виконанні Матильди Поліньської-Левицької та Віктора Бреґі (1903–1976), тенора, згодом оперного режисера. Із запису «Гальки» фірми «Сирена» 1929–1930 років.",
         legal_status="preliminary", legal_work=HALKA_WORK, legal_recording=HALKA_DANA,
         sources=["https://pl.wikipedia.org/wiki/Matylda_Polińska-Lewicka", "https://pl.wikipedia.org/wiki/Wiktor_Brégy",
                  "https://en.wikipedia.org/wiki/Syrena_Rekord"]),
    dict(slug="przytul-uscisnij-pocaluj", ia="78_przytul-ucinij-pocauj-embrace-me-and-kiss-me_mieczylaw-fogg-z-orkiestra-w_gbia0235127b",
         ia_file="PRZYTUL, UŚCIŚNIJ, POCAŁUJ (E - MIECZYLAW FOGG z orkiestra.flac", publish=True,
         title="Przytul, uściśnij, pocałuj", genre="tango",
         composer="Wiktor Krupiński", composer_dates="1879?–1951", lyricist="Andrzej Włast", lyricist_dates="1895–1942/1943",
         performer="Mieczysław Fogg z orkiestrą", label="Syrena-Electro 9369, matryca 25412; egzemplarz: Dana 616-B (wznowienie, 1949)",
         year="1934",
         desc_pl="Sentymentalne tango z 1934 r., wykonywane w warszawskim teatrze „Wielka Rewia”, tu w nagraniu Mieczysława Fogga dla Syreny. Muzyka: Wiktor Krupiński – kompozytor i dyrygent teatrów rewiowych; słowa: Andrzej Włast.\nNota biograficzna do konsultacji z muzykologiem.",
         desc_en="A sentimental tango from 1934, performed at Warsaw's Wielka Rewia theatre, here in Mieczysław Fogg's recording for Syrena. Music by Wiktor Krupiński, composer and revue conductor; lyrics by Andrzej Włast.",
         desc_uk="Сентиментальне танго 1934 року з репертуару варшавського театру «Велике ревю», тут у записі Мєчислава Фогга для фірми «Сирена». Музика Віктора Крупінського, композитора й диригента ревю; слова Анджея Власта.",
         legal_status="preliminary",
         legal_work="Muzyka: Wiktor Krupiński, zm. 19.02.1951 w Warszawie (FilmPolski; data urodzenia niepewna: 1879 lub 1884). Etykiety podają „W. Krupiński”; część źródeł rozwija inicjał jako „Wacław” – identyfikację z Wiktorem Krupińskim podaje staremelodie.pl, do potwierdzenia w zbiorach nut. Słowa: Andrzej Włast, zginął w getcie warszawskim w 1942 lub 1943 r. „R. Nowak” na innych etykietach to śpiewak Robert Nowak, nie współautor. Wstępnie: domena publiczna od 1.01.2022.",
         legal_recording="Nagranie Syrena-Electro z 1934 r. (nr kat. 9369, matryca 25412 wg staremelodie.pl); egzemplarz z Internet Archive to wznowienie Dana z 1949 r. Prawa wykonawców i producenta w Polsce wygasły; status wznowienia Dana w USA do sprawdzenia.",
         sources=[SM + "466/Przytul_uscisnij_pocaluj", "https://staremelodie.pl/kompozytorzy/28/Wiktor_Krupinski",
                  "http://www.filmpolski.pl/fp/index.php/1114831", "https://pl.wikipedia.org/wiki/Andrzej_Włast"]),
    dict(slug="serdeczna-matko", ia="78_serdeczna-matko_pawel-bielanski_gbia0072683a", ia_file="Serdeczna Matko - Pawel Bielanski.flac",
         publish=True,
         title="Serdeczna Matko – pieśń maryjna", genre="piosenka",
         composer="melodia tradycyjna (autor nieznany)", composer_dates="", lyricist="tekst tradycyjny (autor nieznany)", lyricist_dates="",
         performer="Paweł Bielański, z akompaniamentem organów", label="Odeon 11056-A", year="1922",
         desc_pl="Jedna z najpopularniejszych polskich pieśni maryjnych, znana w drukach co najmniej od 1838 r., w akustycznym nagraniu z 1922 r. ze śpiewem przy organach. Wykonawca, Paweł Bielański, nie został dotąd zidentyfikowany – prosimy o informacje.",
         desc_en="One of the most popular Polish Marian hymns, in print since at least 1838, in an acoustic recording from 1922 with organ accompaniment. The singer, Paweł Bielański, has not yet been identified.",
         desc_uk="Одна з найпопулярніших польських марійних пісень, відома в друках щонайменше з 1838 року, в акустичному записі 1922 року в супроводі органа. Виконавця, Павла Бєлянського, поки не ідентифіковано.",
         legal_status="preliminary",
         legal_work="Pieśń anonimowa z XVIII/XIX w.; staremelodie.pl podaje słowa i muzykę jako nieznanego autorstwa, Wikiźródła zawierają druki tekstu z 1838 r. Dla utworu anonimowego ochrona liczy się od pierwszego rozpowszechnienia (art. 36 pkt 3) – upłynęła w XIX w. Utwór w domenie publicznej. Do potwierdzenia: brak chronionego opracowania akompaniamentu organowego (nagranie z 1922 r. – mało prawdopodobne).",
         legal_recording=BIEL_REC,
         sources=[SM + "3421/Serdeczna%20matko", "https://pl.wikisource.org/wiki/Serdeczna_Matko"]),
    # ---- status 'review' (niepewności opisane w karcie) ----
    dict(slug="z-tej-biednej-ziemi", ia="78_z-tej-biednej-ziemi_pawel-bielanski_gbia0072683b", ia_file="Z tej biednej ziemi - Pawel Bielanski.flac",
         publish=False,
         title="Z tej biednej ziemi – pieśń religijna", genre="piosenka",
         composer="do ustalenia (prawdopodobnie melodia tradycyjna)", composer_dates="", lyricist="do ustalenia (prawdopodobnie tekst tradycyjny)", lyricist_dates="",
         performer="Paweł Bielański, z akompaniamentem organów", label="Odeon 11056-B", year="1922",
         desc_pl="Pieśń religijna w akustycznym nagraniu z 1922 r. ze śpiewem przy organach – druga strona płyty z „Serdeczną Matko”. Autorstwo do ustalenia.",
         desc_en="A Polish hymn in an acoustic recording from 1922 with organ accompaniment – the flip side of “Serdeczna Matko”. Authorship to be established.",
         desc_uk="Польська релігійна пісня в акустичному записі 1922 року в супроводі органа – зворотний бік платівки з «Serdeczna Matko». Авторство потрібно встановити.",
         legal_status="candidate",
         legal_work="BRAKUJE: potwierdzenie autorstwa. Pieśń jest zwykle traktowana jako tradycyjna (anonimowa), ale nie znaleźliśmy źródła, które to potwierdza ani które wskazuje autora słów lub melodii. Jeśli autor jest znany – sprawdzić datę śmierci. Do czasu ustalenia bez publikacji.",
         legal_recording=BIEL_REC,
         sources=[]),
    dict(slug="panno-zosiu-ja-funduje", ia="78_panno-zosiu-ja-funduje_orkiestra-syrena-rekord-tadeusz-faliszewski-b-mucman-szl_gbia0315505a",
         ia_file="PANNO ZOSIU, JA FUNDUJE - Orkiestra \"Syrena Rekord\".flac", publish=False,
         title="Panno Zosiu, ja funduję", genre="piosenka",
         composer="Bolesław Mucman", composer_dates="1905–1942/1943", lyricist="Władysław Szlengel", lyricist_dates="1912/1914–1943",
         performer="Tadeusz Faliszewski, Orkiestra „Syrena Rekord”", label="Syrena-Electro (1936); egzemplarz: White Eagle, matryca S-27400",
         year="1936",
         desc_pl="Fokspolka z 1936 r. w wykonaniu Tadeusza Faliszewskiego z orkiestrą Syreny. Muzyka: Bolesław Mucman, słowa: Władysław Szlengel – poeta, który w getcie warszawskim pisał wiersze o jego codzienności. Obaj zginęli w czasie Zagłady.\nNota biograficzna do konsultacji z muzykologiem.",
         desc_en="A fox-polka from 1936 sung by Tadeusz Faliszewski with the Syrena orchestra. Music by Bolesław Mucman, lyrics by Władysław Szlengel, the poet who later chronicled life in the Warsaw Ghetto. Both perished in the Holocaust.",
         desc_uk="Фокс-полька 1936 року у виконанні Тадеуша Фалішевського з оркестром «Сирени». Музика Болеслава Муцмана, слова Владислава Шленгеля – поета, який згодом описував життя Варшавського гетто. Обидва загинули під час Голокосту.",
         legal_status="candidate",
         legal_work="Muzyka: Bolesław Mucman (Micmacher), zginął w Treblince w 1942 lub 1943 r. Słowa: Władysław Szlengel, zginął 8.05.1943 w Warszawie. Obaj w domenie publicznej. BRAKUJE: jedna z innych wersji płytowych (Odeon, śp. Albert Harris) podaje jako współautora tekstu Jerzego Rybę – nie ustaliliśmy, kim był ani kiedy zmarł. Źródła różnią się też numerem katalogowym Syreny (9727 vs SE8810). Do wyjaśnienia przed publikacją.",
         legal_recording="Nagranie Syrena-Electro z 1936 r. (wg staremelodie.pl); egzemplarz z Internet Archive to amerykańskie wznowienie White Eagle (matryca Syreny S-27400). Prawa wykonawców i producenta w Polsce wygasły; status wznowienia w USA do sprawdzenia.",
         sources=[SM + "562/Panno_Zosiu_ja_funduje", "https://pl.wikipedia.org/wiki/Bolesław_Mucman", "https://pl.wikipedia.org/wiki/Władysław_Szlengel"]),
    dict(slug="warszawianka", ia="78_warszawianka_e-mossakowski-w-lachmana-i-akomp-br-szulca_gbia0532833a",
         ia_file="WARSZAWIANKA\" - E. Mossakowski - W. Lachmana i akomp.flac", publish=False,
         title="Warszawianka 1831 roku", genre="chór",
         composer="Karol Kurpiński", composer_dates="1785–1857",
         lyricist="Casimir Delavigne (tekst francuski), Karol Sienkiewicz (przekład polski)", lyricist_dates="1793–1843; 1793–1860",
         performer="Eugeniusz Mossakowski (baryton), chór Wacława Lachmana, orkiestra pod dyr. Bronisława Szulca",
         label="Syrena-Electro 3653 (1931); egzemplarz: White Eagle, matryca S-21751", year="1931",
         desc_pl="Pieśń powstania listopadowego w wykonaniu Eugeniusza Mossakowskiego, barytona Opery Warszawskiej, z chórem Wacława Lachmana i orkiestrą pod dyrekcją Bronisława Szulca. Nagranie Syreny z 1931 r.",
         desc_en="The song of the November Uprising performed by Eugeniusz Mossakowski, baritone of the Warsaw Opera, with Wacław Lachman's choir and an orchestra conducted by Bronisław Szulc. Syrena recording, 1931.",
         desc_uk="Пісня Листопадового повстання у виконанні Євгеніуша Моссаковського, баритона Варшавської опери, з хором Вацлава Лахмана та оркестром під керуванням Броніслава Шульца. Запис «Сирени» 1931 року.",
         legal_status="candidate",
         legal_work="Muzyka: Karol Kurpiński (zm. 1857). Tekst: Casimir Delavigne (zm. 1843), przekład polski Karol Sienkiewicz (zm. 1860). Utwór w domenie publicznej. " + MOSS_ARR,
         legal_recording=MOSS_REC,
         sources=["https://pl.wikipedia.org/wiki/Warszawianka_1831_roku", SM + "2034/Warszawianka",
                  "https://pl.wikipedia.org/wiki/Wacław_Lachman", "https://pl.wikipedia.org/wiki/Bronisław_Szulc",
                  "https://pl.wikipedia.org/wiki/Eugeniusz_Mossakowski"]),
    dict(slug="z-dymem-pozarow", ia="78_z-dymem-poarw_e-mossakowski-w-lachmana-i-akomp-br-szulca_gbia0532833b",
         ia_file="Z DYMEM POŹARÓW\" - E. Mossakowski - W. Lachmana i akomp.flac", publish=False,
         title="Z dymem pożarów (Chorał)", genre="chór",
         composer="Józef Nikorowicz", composer_dates="1827–1890", lyricist="Kornel Ujejski", lyricist_dates="1823–1897",
         performer="Eugeniusz Mossakowski (baryton), chór Wacława Lachmana, orkiestra pod dyr. Bronisława Szulca",
         label="Syrena-Electro (1931); egzemplarz: White Eagle, matryca S-21650", year="1931",
         desc_pl="„Chorał” Kornela Ujejskiego z muzyką Józefa Nikorowicza – jedna z najważniejszych polskich pieśni patriotycznych XIX w. Śpiewa Eugeniusz Mossakowski z chórem Wacława Lachmana; druga strona płyty z „Warszawianką”.",
         desc_en="Kornel Ujejski's “Chorale” set by Józef Nikorowicz, one of the most important Polish patriotic hymns of the 19th century, sung by Eugeniusz Mossakowski with Wacław Lachman's choir; flip side of “Warszawianka”.",
         desc_uk="«Хорал» Корнеля Уєйського на музику Юзефа Никоровича – одна з найважливіших польських патріотичних пісень XIX століття. Співає Євгеніуш Моссаковський з хором Вацлава Лахмана; зворотний бік платівки з «Варшав'янкою».",
         legal_status="candidate",
         legal_work="Muzyka: Józef Nikorowicz (zm. 1890). Słowa: Kornel Ujejski (zm. 1897). Utwór w domenie publicznej. " + MOSS_ARR,
         legal_recording=MOSS_REC,
         sources=["https://pl.wikipedia.org/wiki/Z_dymem_pożarów", "http://www.staremelodie.pl/piosenka/3105/Z_dymem_pozarow",
                  "https://pl.wikipedia.org/wiki/Wacław_Lachman", "https://pl.wikipedia.org/wiki/Bronisław_Szulc"]),
    dict(slug="i-ty-mu-wierzysz", ia="78_itymuwierzysz_245_16", ia_file="Itymuwierzysz - Stanislaw Gruszczynski - Stanislav Moniuszko.flac",
         publish=False, source_name=IA78 + " (78-opera)",
         title="I ty mu wierzysz – dumka Jontka z opery „Halka”", genre="aria operowa",
         composer="Stanisław Moniuszko", composer_dates="1819–1872", lyricist="Włodzimierz Wolski (libretto)", lyricist_dates="1824–1882",
         performer="Stanisław Gruszczyński (tenor), z orkiestrą", label="Syrena 3118, matryca 18995 (wg opisu IA)",
         year="ok. 1920 (wg opisu IA – niepotwierdzone)",
         desc_pl="Dumka Jontka z II aktu „Halki” w wykonaniu Stanisława Gruszczyńskiego (1891–1959), tenora Opery Warszawskiej od 1916 r. Datę nagrania trzeba potwierdzić.",
         desc_en="Jontek's dumka from Act II of Halka sung by Stanisław Gruszczyński (1891–1959), a Warsaw Opera tenor from 1916. The recording date needs confirmation.",
         desc_uk="Думка Йонтека з II дії «Гальки» у виконанні Станіслава Грушчинського (1891–1959), тенора Варшавської опери з 1916 року. Дату запису потрібно підтвердити.",
         legal_status="candidate",
         legal_work=HALKA_WORK + " Status „kandydat” wynika wyłącznie z niepewnej daty nagrania (patrz niżej).",
         legal_recording="Internet Archive datuje płytę na 1920 r. (Syrena 3118), ale nie znaleźliśmy potwierdzenia: Wikipedia wymienia płyty Gruszczyńskiego dla Syreny z lat 1926, 1932, 1937 i 1939. Śpiewak występował w Warszawie od 1916 r., więc nagranie może pochodzić sprzed 1918 r. – poza zakresem kolekcji. Prawa do nagrania w każdym wariancie wygasły. BRAKUJE: datowanie z katalogu Syreny.",
         sources=["https://pl.wikipedia.org/wiki/Stanisław_Gruszczyński"]),
    dict(slug="gdy-sie-chrystus-rodzi", ia="78_gdy-sie-chrystus-rodzi_chor-im-sw-cecylii-f-nowowiejski-ks-b-kopec_gbia0278594a",
         ia_file="GDY SIE CHRYSTUS RODZI - CHOR IM. SW. CECYLII.flac", publish=False,
         title="Gdy się Chrystus rodzi – kolęda w opracowaniu Feliksa Nowowiejskiego", genre="chór",
         composer="melodia tradycyjna, opr. Feliks Nowowiejski", composer_dates="1877–1946",
         lyricist="tekst tradycyjny", lyricist_dates="",
         performer="Chór im. św. Cecylii; na etykiecie także „Ks. B. Kopeć” (rola do ustalenia)",
         label="matryca T-31164 (wytwórnia nieczytelna; wg staremelodie.pl Victor)", year="do ustalenia",
         desc_pl="Kolęda w opracowaniu chóralnym Feliksa Nowowiejskiego, autora muzyki do „Roty”. Chór, data i miejsce nagrania wymagają ustalenia – możliwe, że to chór polonijny z Ameryki Północnej.",
         desc_en="A Polish Christmas carol in a choral arrangement by Feliks Nowowiejski, composer of “Rota”. The choir, date and place of recording are still to be established – possibly a Polish-American choir.",
         desc_uk="Польська колядка в хоровому опрацюванні Фелікса Нововейського, автора музики до «Роти». Хор, дату й місце запису ще потрібно встановити – можливо, це хор польської діаспори в Північній Америці.",
         legal_status="candidate",
         legal_work="Melodia i tekst tradycyjne; opracowanie: Feliks Nowowiejski (zm. 18.01.1946) – w domenie publicznej. BRAKUJE: rola „Ks. B. Kopeć” na etykiecie. Jeśli to autor innego opracowania (a nie dyrygent), trzeba ustalić jego datę śmierci – jedyny znaleziony kandydat, ks. Bronisław Kopeć z Filadelfii, zmarł w 1968 r. (identyfikacja niepotwierdzona; w takim wariancie opracowanie byłoby chronione do końca 2038 r.).",
         legal_recording="BRAKUJE: data i miejsce nagrania. Wg staremelodie.pl płyta Victor (czarna etykieta, seria etniczna), wg komentarza – tłoczenie na zamówienie w Kanadzie; nagranie może pochodzić spoza Polski i spoza lat 1918–1939. Status w USA/Kanadzie do sprawdzenia.",
         sources=["https://polskabibliotekamuzyczna.pl/encyklopedia/nowowiejski-feliks/", SM + "2886/Gdy_sie_Chrystus_rodzi",
                  SM + "5991/Noc_cicha_w_snie"]),
]

# Zmiany w istniejącej liście kandydatów (klucz: dotychczasowy tytuł z app/seed.py).
# (tytuł, muzyka, słowa, nagranie, źródło, status wstępny, uwagi)
IA = "https://archive.org/details/"
POLONIA = "Egzemplarz IA to płyta Polonia (Orbis, Londyn) – wytwórnia emigracyjna działająca po 1945 r.; nagranie najpewniej spoza zakresu 1918–1939."
CANDIDATES_UPDATE = {
    "Twe smutne oczy (tango)": ("Twe smutne oczy (tango)", "Jakub Kagan (1896–1942)", "Andrzej Włast (1895–1942/43)", "J. Czerwińska, Ork. R. Franka (Polonia, Londyn)", IA + "78_twe-smutne-oczy_jadwiga-czerwinska-orkiestra-taneczna-ryszarda-franka-j-kagan-a-w_gbia0474838a", "prawdopodobnie DP (utwór)", "W prototypie. " + POLONIA + " Na stronie B „Romans wojenny” (Hemar) – utwór z czasów wojny. Do weryfikacji daty nagrania; ewentualnie zastąpić nagraniem przedwojennym."),
    "Szkoda twoich łez, dziewczyno (1929)": ("Szkoda twoich łez, dziewczyno (1929)", "Artur Gold (1897–1943) wg IU / „H. Gold” na etykiecie", "Andrzej Włast", "Ich Pięciu, Ork. R. Franka (Polonia, Londyn)", IA + "78_szkoda-twoich-lez_ich-pieciu-orkiestra-taneczna-ryszarda-franka-h-gold-a-wlan_gbia0474835a", "WSTRZYMANY", "Sprzeczna atrybucja: jeśli Henryk Gold (zm. 1977) – chroniony do końca 2047. " + POLONIA),
    "Tango dla mojej matki": ("Tango dla mojej matki", "Zygmunt Białostocki (1897–1942)", "do ustalenia", "Ork. R. Franka, Gwido Borucki (Polonia, Londyn)", IA + "78_tango-dla-mojej-matki-tango-for-my-mother_orkiestra-taneczna-ryszrda-franka-gwido_gbia3011472a", "do weryfikacji", "Ustalić autora tekstu. " + POLONIA + " Druga kopia (A. Jędrzejowski) datowana 1953."),
    "Przytul, uściśnij, pocałuj": ("Przytul, uściśnij, pocałuj (tango, 1934)", "Wiktor Krupiński (1879?–1951)", "Andrzej Włast (1895–1942/43)", "Mieczysław Fogg, Syrena-Electro 9369 (1934); kopia Dana 616-B", IA + "78_przytul-ucinij-pocauj-embrace-me-and-kiss-me_mieczylaw-fogg-z-orkiestra-w_gbia0235127b", "prawdopodobnie DP", "W prototypie (opublikowany). „R. Nowak” to śpiewak Robert Nowak, nie autor. Inicjał „W.” bywa rozwijany jako „Wacław” – potwierdzić w nutach."),
    "Nie płacz baby": ("Nie płacz, baby (walc)", "Szymon Kataszek (1898–1943)", "Aleksander Jellin (1904–ok. 1994)", "Mieczysław Fogg z orkiestrą (kopia Dana 607-A)", IA + "78_nie-pacz-baby-dont-cry-baby_mieczysaw-fogg-z-orkiestra-kataszek-jellin_gbia0434944a", "NIE", "Wykluczony: autor tekstu zm. ok. 1994 – tekst chroniony do ok. 2064. Muzyka Kataszka w DP (wersja instrumentalna możliwa)."),
    "Maruszka": ("Maruszka (tango, 1935)", "Joop de Leur (1900–1973)", "Andrzej Włast (pol.); oryginał niemiecki – autor do ustalenia", "Mieczysław Fogg, Syrena-Electro 9536 (1935); kopia White Eagle", IA + "78_maruszka_mieczysaw-fogg-ork-syrena-rekord-j-de-leur-wast_gbia0531378a", "NIE", "Wykluczony: kompozytor zm. 1973 – chroniony do końca 2043."),
    "Ti-Pi-Tin (wersja polska)": ("Ti-Pi-Tin (wersja polska)", "María Grever (1885–1951)", "Andrzej Włast (pol.)", "Ich Pięciu, Mały zespół R. Franka (Polonia, Londyn)", IA + "78_ti-pi-ton_ich-pieciu-maly-zespol-taneczny-ryszarda-franka-m-grever-a-wlast_gbia0474785a", "do analizy", "Czy polski tekst jest tłumaczeniem oryginału hiszpańskiego (Grever) czy angielskiego (R. Leveen)? " + POLONIA),
    "Pamiętasz Capri (wersja polska)": ("Pamiętasz Capri (wersja polska)", "Will Grosz (1894–1939)", "Andrzej Włast (pol.)", "Ich Pięciu, Ork. R. Franka (Polonia, Londyn)", IA + "78_pamietasz-capri-the-isle-of-capri_ich-pieciu-maly-zespol-taneczny-ryszarda-franka_gbia0474786a", "do analizy", "Muzyka DP; czy tekst Własta jest opracowaniem tekstu J. Kennedy'ego (zm. 1984)? " + POLONIA),
    "Gdyby rannym słonkiem (Halka)": ("Gdyby rannym słonkiem (Halka)", "Stanisław Moniuszko", "Włodzimierz Wolski", "Matylda Polińska-Lewicka, Ork. Opery Warszawskiej (Syrena 1929–30, kopia Dana)", IA + "78_gdyby-rannym-slonkeim_matylda-polinska-lewicka-z-ork-opery-warszawkseij-st.-moniusz_gbia0007666a", "DP (utwór)", "W prototypie (opublikowany), razem z „O mój maleńki” i duetem „Niechaj będzie pochwalony”. Status wydania Dana w USA."),
    "Kozak": ("Kozak", "Stanisław Moniuszko", "Jan Czeczot (1796–1847) wg POLMIC; dawniej podawano W. Syrokomlę", "Adam Didur, Brunswick 60049-B, 1928 (USA)", IA + "78_kozakthecossack_217_12", "DP (utwór)", "W prototypie (opublikowany), razem z „Pieśnią Chorążego”. Nagranie amerykańskie – w USA chronione do końca 2028 r."),
    "Gdy się Chrystus rodzi (kolęda)": ("Gdy się Chrystus rodzi (kolęda)", "trad., opr. Feliks Nowowiejski (1877–1946)", "trad.", "Chór im. św. Cecylii, „Ks. B. Kopeć” (Victor?)", IA + "78_gdy-sie-chrystus-rodzi_chor-im-sw-cecylii-f-nowowiejski-ks-b-kopec_gbia0278594a", "do weryfikacji", "W prototypie (status review). Ustalić rolę „Ks. B. Kopeć” oraz datę i kraj nagrania (prawdopodobnie Ameryka Północna)."),
    "Rota": ("Rota", "Feliks Nowowiejski (1877–1946)", "Maria Konopnicka (1842–1910)", "E. Mossakowski z chórem W. Lachmana, Syrena-Electro 1931", IA + "MyPierwszaBrygadaRotaEugeniuszMossakowskiZUdz.Choru", "DP (utwór)", "Nagranie z epoki odnalezione, ale w IA tylko jako MP3 wgrane przez prywatnego użytkownika (z deklarowaną licencją CC BY-NC-SA) – nie pobrano. Szukać transferu FLAC."),
}
CANDIDATES_NEW = [
    ("Pieśń Chorążego (Hrabina)", "Stanisław Moniuszko", "Włodzimierz Wolski", "Adam Didur, Brunswick 60049-A, 1928 (USA)", IA + "78_songoftheemblem-bearer_217_11", "DP (utwór)", "W prototypie (opublikowany). Nagranie amerykańskie – w USA chronione do końca 2028 r."),
    ("Serdeczna Matko", "trad.", "trad. (druki od 1838)", "Paweł Bielański z organami, Odeon 11056-A, 1922", IA + "78_serdeczna-matko_pawel-bielanski_gbia0072683a", "DP (utwór)", "W prototypie (opublikowany). Ustalić tożsamość śpiewaka i miejsce nagrania."),
    ("Z tej biednej ziemi", "do ustalenia (trad.?)", "do ustalenia (trad.?)", "Paweł Bielański z organami, Odeon 11056-B, 1922", IA + "78_z-tej-biednej-ziemi_pawel-bielanski_gbia0072683b", "do weryfikacji", "W prototypie (status review). Potwierdzić anonimowość pieśni."),
    ("Panno Zosiu, ja funduję (fokspolka, 1936)", "Bolesław Mucman (1905–1942/43)", "Władysław Szlengel (1912/14–1943); Jerzy Ryba?", "Tadeusz Faliszewski, Ork. Syrena Rekord (kopia White Eagle)", IA + "78_panno-zosiu-ja-funduje_orkiestra-syrena-rekord-tadeusz-faliszewski-b-mucman-szl_gbia0315505a", "do weryfikacji", "W prototypie (status review). Ustalić, czy Jerzy Ryba (podany na innej płycie) jest współautorem tekstu, i jego daty."),
    ("Warszawianka 1831 roku", "Karol Kurpiński (1785–1857)", "C. Delavigne (1793–1843), przekł. K. Sienkiewicz (1793–1860)", "E. Mossakowski, chór W. Lachmana, dyr. B. Szulc, Syrena-Electro 1931 (kopia White Eagle)", IA + "78_warszawianka_e-mossakowski-w-lachmana-i-akomp-br-szulca_gbia0532833a", "do weryfikacji", "W prototypie (status review). Utwór DP; ustalić autora opracowania (Lachman zm. 1963 – chronione do 2033; Szulc zm. 1955 – DP)."),
    ("Z dymem pożarów (Chorał)", "Józef Nikorowicz (1827–1890)", "Kornel Ujejski (1823–1897)", "E. Mossakowski, chór W. Lachmana, dyr. B. Szulc, Syrena-Electro 1931 (kopia White Eagle)", IA + "78_z-dymem-poarw_e-mossakowski-w-lachmana-i-akomp-br-szulca_gbia0532833b", "do weryfikacji", "W prototypie (status review). Jak wyżej – autor opracowania."),
    ("I ty mu wierzysz (Halka)", "Stanisław Moniuszko", "Włodzimierz Wolski", "Stanisław Gruszczyński, Syrena 3118 (IA: 1920)", IA + "78_itymuwierzysz_245_16", "DP (utwór)", "W prototypie (status review). Potwierdzić datę nagrania – może pochodzić sprzed 1918 r."),
    ("O mój maleńki / Niechaj będzie pochwalony (Halka)", "Stanisław Moniuszko", "Włodzimierz Wolski", "M. Polińska-Lewicka, W. Brégy, Ork. Opery Warszawskiej (Syrena 1929–30, kopie Dana 6002-B, 6005-A)", IA + "78_niechaj-bedzie-pochwalony_matylda-polinska-lewicka-w.-bregy--opery-warszawskiej_gbia0007562a", "DP (utwór)", "W prototypie (opublikowane). Status wydania Dana w USA."),
    ("Boże, stwórco nasz Panie / Ave Maria", "do ustalenia", "do ustalenia", "Paweł Bielański; Wanda Hendrichówna, Odeon 11094, 1923", IA + "78_boze-stworco-nasz-panie_pawel-bielanski_gbia0072682a", "do weryfikacji", "Nie importowano: autorstwo (i kompozytor „Ave Maria”) nieustalone."),
    ("Jak zabawa to zabawa / Sto lat / Siup, Maryśka", "Lewandowski; Krupiński (?)", "Jerry, Szlengel; Chrzanowski; Wereszczyńska", "Tadeusz Faliszewski (Syrena, kopie Dana 602/604)", IA + "78_jak-zabawa-to-zabawa-if-its-fun-its-really-fun_tadeusz-faliszewski-lewandowski_gbia0267841b", "do weryfikacji", "Ustalić tożsamość i daty współautorów."),
    ("Odrobina szczęścia", "Jerzy Petersburski (1895–1979)", "Emanuel Schlechter (1904–1943)", "Mieczysław Fogg, Syrena", IA + "78_odrobina-szczescia--a-bit-of-happiness_mieczyslaw-fogg-z-orkiestra-syrena-records_gbia0002198a", "NIE", "Wykluczony: kompozytor zm. 1979 – chroniony do końca 2049."),
    ("Śmiej się, Griszka!", "Oskar Strok (1893–1975)", "Władysław Szlengel", "Mieczysław Fogg, Ork. Syrena Rekord (kopia White Eagle)", IA + "78_miej-si-griszka-lets-laugh_orkiestra-tan-syrena-rekord-mieczyslaw-fogg-o-strock-w-s_gbia0529662b", "NIE", "Wykluczony: kompozytor zm. 1975 – chroniony do końca 2045."),
    ("Cicho, grajcie mi znów", "Cesare Andrea Bixio (1896–1978)", "do ustalenia (pol.)", "Mieczysław Fogg, Ork. Syrena Rekord (kopia White Eagle)", IA + "78_cicho-grajcie-mi-znw-play-it-softly-once-more_orkiestra-syrena-rekord-mieczyslaw-fo_gbia0529361a", "NIE", "Wykluczony: kompozytor zm. 1978."),
    ("Taki ktoś jak ty", "Seller (do ustalenia)", "Jerzy Jurandot (1911–1979)", "Mieczysław Fogg", IA + "78_taki-kto-jak-ty-someone-like-you_mieczysaw-fogg-seller-jurandot_gbia0531293b", "NIE", "Wykluczony: autor tekstu zm. 1979."),
    ("Miasteczko Bełz", "Alexander Olshanetsky (1892–1946)", "Jacob Jacobs (1890–1977), pol. tekst do ustalenia", "Adam Aston, Ork. Syrena-Rekord", IA + "78_miasteczko-bez_aston-ork-syrena-rekord-burstein-n-lith-freg-roman_gbia0530904b", "NIE", "Wykluczony: autor oryginalnego tekstu zm. 1977. Etykieta podaje inne nazwiska (Burstein, N. Lith Freg, Roman) – role do ustalenia, ale oryginał i tak chroniony."),
    ("Oczy czarne / Bo ta pierwsza miłość", "Henryk Gold (1899–1977); Ralph Benatzky (1884–1957)", "Marian Hemar (1901–1972)", "Zofia Terne, Ork. R. Franka (Polonia, Londyn)", "", "NIE", "Wykluczone: chronieni twórcy; ponadto nagrania powojenne."),
    ("Piosnka Broni (Hrabina) / Życzenie (Chopin)", "S. Moniuszko; F. Chopin", "W. Wolski; S. Witwicki (1801–1847)", "Lucyna Szczepańska, Jerzy Kropiwnicki (Polonia, Londyn)", IA + "78_pionska-broni-bronias-song_lucyna-szczepanska-jerzy-kropiwnicki-hrabina-s.-mon_gbia0002285a", "DP (utwór)", "Nie importowano: nagranie powojenne (Polonia, Londyn) – poza zakresem 1918–1939."),
    ("Nagrania Chóru Dana (Dana Records, 1946–1953)", "różni", "różni", "Chór Dana, Nowy Jork", "", "poza zakresem", "Nagrania powojenne – poza zakresem kolekcji (choć Dana wznawiała też przedwojenne matryce Syreny)."),
]

LAWYER_NOTES = [
    "1. **Płyty Polonia (Londyn)**: wytwórnia Orbis (Polonia) Ltd. działała po 1945 r.; nagrania Orkiestry Ryszarda Franka, „Ich Pięciu”, J. Czerwińskiej, Z. Terne, G. Boruckiego pochodzą najpewniej z lat 40.–50. Dotyczy to opublikowanego już nagrania „Twe smutne oczy” – opis „lata 30.” jest prawdopodobnie błędny. Prosimy o ocenę praw do takiego fonogramu (ok. 1946–1957) i decyzję, czy pozostawić je w katalogu.",
    "2. **Nagrania amerykańskie z 1928 r.** (A. Didur, Brunswick): w Polsce prawa wygasły, w USA ochrona do 31.12.2028 – czy wymagana blokada geograficzna?",
    "3. **Wznowienia Dana i White Eagle** (USA) przedwojennych matryc Syreny (Halka 1929–30, Fogg 1934, Mossakowski 1931, Faliszewski 1936): czy kopia z amerykańskiego wznowienia zmienia ocenę praw do nagrania w USA?",
    "4. **Opracowania (aranżacje)**: przy nagraniach chóralnych (Mossakowski, chór Lachmana; Chór im. św. Cecylii) autor opracowania nie jest podany. Jak postępować, gdy możliwy autor opracowania zmarł po 1955 r.?",
    "5. **Pieśni anonimowe** („Serdeczna Matko”, „Z tej biednej ziemi”): czy wystarczy ustalenie, że utwór był rozpowszechniony w XIX w. (art. 36 pkt 3)?",
    "6. **Andrzej Włast**: Wikipedia podaje śmierć w getcie warszawskim w 1942 lub 1943 r.; nie znaleźliśmy potwierdzenia wariantu 1944–1946. W każdym wariancie domena publiczna.",
    "7. Wszystkie karty prawne nowych nagrań to wstępna analiza, nie opinia prawna. Nagrania ze statusem „kandydat” są niewidoczne publicznie (status `review`) do czasu wyjaśnienia braków opisanych w karcie.",
]


def ia_url(t):
    return f"https://archive.org/details/{t['ia']}"


def download(t):
    out = os.path.join(ORIG, t["slug"] + ".flac")
    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        return out
    url = f"https://archive.org/download/{t['ia']}/{urllib.parse.quote(t['ia_file'])}"
    print("pobieram", t["slug"], flush=True)
    tmp = out + ".part"
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, out)
    return out


ROW_KEYS = ["slug", "title", "genre", "composer", "composer_dates", "lyricist", "lyricist_dates", "performer", "label",
            "year", "source_name", "source_url", "desc_pl", "desc_en", "desc_uk", "legal_status", "legal_work", "legal_recording"]


def row_of(t):
    r = {k: t.get(k, "") for k in ROW_KEYS}
    r["source_url"] = ia_url(t)
    r["source_name"] = t.get("source_name", GB)
    r["legal_work"] = t["legal_work"].strip() + "\n" + NOTE
    return r


def upsert(c, t):
    r = row_of(t)
    sources = [ia_url(t)] + [s for s in t["sources"] if s != ia_url(t)]
    tr = c.execute("SELECT * FROM tracks WHERE slug=?", (t["slug"],)).fetchone()
    if not tr:
        cols = list(r) + ["legal_sources", "legal_date", "status", "created"]
        c.execute(f"INSERT INTO tracks({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                  (*r.values(), json.dumps(sources, ensure_ascii=False), TODAY, "draft", A.now()))
    else:
        changed = any((tr[k] or "") != r[k] for k in ("legal_status", "legal_work", "legal_recording")) \
            or json.loads(tr["legal_sources"] or "[]") != sources
        sets = [k for k in r if k != "slug"]
        c.execute(f"UPDATE tracks SET {','.join(k + '=?' for k in sets)}, legal_sources=?, legal_version=?, legal_date=? WHERE slug=?",
                  (*[r[k] for k in sets], json.dumps(sources, ensure_ascii=False),
                   tr["legal_version"] + (1 if changed else 0), TODAY if changed else tr["legal_date"], t["slug"]))
    c.commit()
    return c.execute("SELECT * FROM tracks WHERE slug=?", (t["slug"],)).fetchone()


def target_status(t):
    return "published" if t["publish"] else "review"


def process(c, tr, src):
    jid = A.enqueue_catalog(c, tr["id"], src)
    # serwer aplikacji ma własny wątek kolejki – oznaczamy zadanie jako uruchomione, zanim je zobaczy
    c.execute("UPDATE jobs SET status='running' WHERE id=?", (jid,))
    c.execute("UPDATE tracks SET abc=NULL WHERE id=?", (tr["id"],))
    c.commit()
    print("przetwarzam", tr["slug"], flush=True)
    A.run_job(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    j = c.execute("SELECT status, message FROM jobs WHERE id=?", (jid,)).fetchone()
    if j["status"] != "done":
        print("  BŁĄD:", j["message"], flush=True)
        c.execute("UPDATE tracks SET status='review' WHERE id=?", (tr["id"],))
        c.commit()
        return False
    p = json.loads(c.execute("SELECT processing FROM tracks WHERE id=?", (tr["id"],)).fetchone()[0])
    print("  redukcja szumu:", p.get("denoise", {}).get("noise_reduction_db"), "dB; udział wokalu:", p.get("vocal_ratio"), flush=True)
    return True


def sync_candidates(c):
    for old_title, row in CANDIDATES_UPDATE.items():
        if c.execute("SELECT 1 FROM candidates WHERE title=?", (old_title,)).fetchone():
            c.execute("UPDATE candidates SET title=?,composer=?,lyricist=?,recording=?,source=?,status=?,note=? WHERE title=?",
                      (*row, old_title))
        elif not c.execute("SELECT 1 FROM candidates WHERE title=?", (row[0],)).fetchone():
            c.execute("INSERT INTO candidates(title,composer,lyricist,recording,source,status,note) VALUES(?,?,?,?,?,?,?)", row)
        else:
            c.execute("UPDATE candidates SET composer=?,lyricist=?,recording=?,source=?,status=?,note=? WHERE title=?",
                      (*row[1:], row[0]))
    for row in CANDIDATES_NEW:
        if c.execute("SELECT 1 FROM candidates WHERE title=?", (row[0],)).fetchone():
            c.execute("UPDATE candidates SET composer=?,lyricist=?,recording=?,source=?,status=?,note=? WHERE title=?",
                      (*row[1:], row[0]))
        else:
            c.execute("INSERT INTO candidates(title,composer,lyricist,recording,source,status,note) VALUES(?,?,?,?,?,?,?)", row)
    c.commit()


def write_md():
    """Dokument dla prawnika: lista z seed.py z naniesionymi zmianami + nowe pozycje + uwagi z importu."""
    import seed
    base = list(seed.CANDIDATES)
    updated = [CANDIDATES_UPDATE.get(r[0], r) for r in base]
    titles = {r[0] for r in updated}
    seed.CANDIDATES = updated + [r for r in CANDIDATES_NEW if r[0] not in titles]
    try:
        seed.write_candidates_md()
    finally:
        seed.CANDIDATES = base
    p = os.path.join(ROOT, "docs", "kandydaci-domena-publiczna.md")
    with open(p, "a") as f:
        f.write("\n".join(["", "## Uwagi z importu nagrań (12.11.2026)", ""] + LAWYER_NOTES + [""]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--reprocess", action="store_true")
    ap.add_argument("--no-process", action="store_true")
    ap.add_argument("--skip-missing", action="store_true", help="przetwarzaj tylko utwory z pobranym już plikiem FLAC")
    a = ap.parse_args()
    only = {s for s in a.only.split(",") if s}
    A.init_db()
    c = A.raw_db()
    sync_candidates(c)
    write_md()
    summary = []
    for t in TRACKS:
        if only and t["slug"] not in only:
            continue
        tr = upsert(c, t)
        have = os.path.exists(os.path.join(ORIG, t["slug"] + ".flac"))
        if not a.no_process and (a.reprocess or not tr["processing"]) and (have or not a.skip_missing):
            try:
                src = download(t)
            except Exception as e:
                print("  nie udało się pobrać", t["slug"], e, flush=True)
                continue
            if not process(c, tr, src):
                continue
        if c.execute("SELECT processing FROM tracks WHERE slug=?", (t["slug"],)).fetchone()[0]:
            c.execute("UPDATE tracks SET status=? WHERE slug=?", (target_status(t), t["slug"]))
            c.commit()
        tr = c.execute("SELECT * FROM tracks WHERE slug=?", (t["slug"],)).fetchone()
        dn = json.loads(tr["processing"] or "{}").get("denoise", {})
        summary.append((tr["title"], tr["legal_status"], tr["status"], dn.get("noise_reduction_db")))
    c.close()
    print("\nPodsumowanie:")
    for s in summary:
        print(" | ".join(str(x) for x in s))


if __name__ == "__main__":
    main()
