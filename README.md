# Fonoteka – prototyp

Otwarte, bezpłatne archiwum polskich nagrań z lat 1918–1939 w domenie publicznej: katalog, karta prawna, osobne ścieżki (stemy), szkic zapisu nutowego, separator dla nagrań użytkowników, konta z biblioteką i społeczność. Interfejs PL / EN / UA. Wygląd jest celowo neutralny – warstwa wizualna przyjdzie później (zmienne w `app/static/style.css`).

## Uruchomienie

```bash
cd fonoteka
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python flask "torch==2.5.1" "torchaudio==2.5.1" demucs soundfile numpy librosa
.venv/bin/python app/seed.py      # konta testowe, 3 nagrania (separacja trwa kilka minut), blog, lista kandydatów
.venv/bin/python app/app.py       # http://127.0.0.1:5055
```

Wymaga `ffmpeg`. Konta testowe (z hasłami) zapisuje `seed.py` w `data/konta-testowe.txt`.

## Co jest w środku

| Obszar | Pliki |
|---|---|
| Serwer, baza (SQLite), konta, pobieranie, kolejka zadań | `app/app.py` |
| Odszumianie szelaku i winylu (FFmpeg, bez AI) | `app/denoise.py` |
| Separacja (Demucs htdemucs, MIT), poprzedzona odszumianiem | `app/separator.py` |
| Szkic nut: melodia z wokalu (pYIN), akordy z podkładu (chroma) → ABC | `app/transcribe.py` |
| Teksty interfejsu PL/EN/UA | `app/i18n.py` |
| Widoki | `app/templates/` |
| Mikser stemów (Web Audio) | `app/static/mixer.js` |
| Lista kandydatów dla prawnika | `docs/kandydaci-domena-publiczna.md` |

## Odszumianie – zwykły program, bez agenta AI

`app/denoise.py` to klasyczne przetwarzanie sygnału (FFmpeg): filtr dudnienia, przydźwięk 50 Hz (opcja), usuwanie trzasków (`adeclick`), odejmowanie widma szumu z profilem pobranym automatycznie z najcichszego fragmentu (`afftdn`), ograniczenie pasma, stała normalizacja głośności. Trzy tryby: szelak 78 obr./min, winyl, łagodny; trzy poziomy siły. Działa w kilka sekund na CPU. Na nagraniach testowych szum w ciszy spadł o 10–26 dB.

Dostępne jako osobne narzędzie (`/odszumianie`, odsłuch przed/po) i jako krok przed separacją (wybór nośnika w separatorze). Z wiersza poleceń:

```bash
.venv/bin/python app/denoise.py wejscie.flac wynik.wav szelak
```

## Wersja demonstracyjna na Cloudflare

Adres główny: **https://fonoteka-pl.pages.dev** (Cloudflare Pages połączone z repozytorium GitHub `Lumerw/fonoteka`; nazwa `fonoteka.pages.dev` była już zajęta).
Stary adres https://fonoteka.teraz-platforma.workers.dev (Workers, ręczny `npx wrangler deploy`) nadal działa, ale nie aktualizuje się sam.

### Jak działa automatyczne wdrożenie

Cloudflare Pages nie ma dostępu do bazy (`data/`) ani nagrań (`media/`), więc **nic nie buduje** – publikuje gotowy katalog `dist/`, który jest w repozytorium.
Ustawienia projektu `fonoteka-pl`: gałąź produkcyjna `main`, framework *None*, bez komendy build, katalog wyjściowy `dist`.

```bash
.venv/bin/python app/export_static.py      # 1. buduje dist/ (PL, /en, /uk) – tylko utwory opublikowane
git add dist && git commit -m "Aktualizacja wersji demo"   # 2. commit gotowej strony
git push                                    # 3. push na main → Pages wdraża sam (ok. 1 min)
```

- Status wdrożeń: panel Cloudflare → Workers & Pages → `fonoteka-pl` → Deployments, albo `npx wrangler pages deployment list --project-name fonoteka-pl`.
- Push na inną gałąź tworzy wersję podglądową pod adresem `<gałąź>.fonoteka-pl.pages.dev` (produkcja się nie zmienia).
- Limity: pojedynczy plik ≤ 25 MB (Pages), ≤ 100 MB (GitHub), do 20 000 plików. Obecnie `dist/` ma ok. 120 MB i pliki MP3 do ~3,5 MB.
- Nagłówki (`X-Robots-Tag: noindex`) są w `dist/_headers`, strona błędu w `dist/404.html` – oba generuje `export_static.py`.
- `wrangler.jsonc` dotyczy tylko starego wdrożenia Workers; Pages go pomija.

### Własna domena (np. fonoteka.org) – po zakupie

1. Cloudflare → Workers & Pages → `fonoteka-pl` → **Custom domains** → *Set up a custom domain* → wpisz `fonoteka.org` (i osobno `www.fonoteka.org`).
2. DNS:
   - **Domena przeniesiona do Cloudflare (zalecane, wymagane dla domeny głównej bez `www`)**: Cloudflare → *Add a domain* → u rejestratora zmień serwery nazw na te podane przez Cloudflare. Po aktywacji strefy Pages sam doda rekordy, a certyfikat HTTPS wystawi się automatycznie.
   - **DNS zostaje u rejestratora**: da się podpiąć tylko subdomenę (np. `www.fonoteka.org`) – dodaj u rejestratora rekord `CNAME www → fonoteka-pl.pages.dev` i dopiero potem zatwierdź domenę w Pages. Domeny głównej (apex) w ten sposób nie podepniesz.
3. Przekierowania na nową domenę:
   - `fonoteka-pl.pages.dev` → domena: Cloudflare → *Rules* → *Bulk Redirects* (lista: `fonoteka-pl.pages.dev` → `https://fonoteka.org`, 301, z zachowaniem ścieżki i parametrów). Nie przekierowuj adresów podglądowych `*.fonoteka-pl.pages.dev`.
   - `www` → domena główna: reguła *Redirect Rules* w strefie `fonoteka.org`.
   - Stary adres Workers: najprościej usunąć projekt Workers `fonoteka` (panel → Workers & Pages → `fonoteka` → Settings → Delete) albo podmienić go na Worker zwracający `301` na nową domenę.
4. Zaktualizuj adres w README i we wniosku. Gdy prawnik potwierdzi status nagrań i strona ma być indeksowana – usuń `X-Robots-Tag` i `Disallow` z `export_static.py`.

### Ręcznie, bez GitHuba (stara metoda)

```bash
.venv/bin/python app/export_static.py
npx wrangler deploy                        # Workers: fonoteka.teraz-platforma.workers.dev (wrangler.jsonc)
```

Wersja statyczna: odsłuch, mikser, karty prawne, nuty, blog, społeczność (do czytania). Formularze są wyłączone. Strona ma `noindex` do czasu opinii prawnej o redystrybucji plików. Pełna aplikacja (konta, pobieranie, separator, odszumianie) wymaga serwera z Pythonem i FFmpeg – Cloudflare Pages/Workers jej nie uruchomi.

## Kiedy rozdzielamy ścieżki – decyzja

* **Katalog: przy dodawaniu nagrania (raz).** Realizator odsłuchuje stemy, a prawnik zatwierdza kartę, zanim cokolwiek trafi do publicznego katalogu (status `review` → `published`). Pobieranie jest natychmiastowe, koszt GPU jest jednorazowy i przewidywalny (30 nagrań), a każdy pobrany plik ma stałą sumę SHA-256 w potwierdzeniu pobrania.
* **Separator dla użytkowników: na żądanie, w kolejce.** Pliki są prywatne, limit 5 minut, usuwane po 24 h.
* Na żądanie dla katalogu nie ma sensu: każde pobranie liczyłoby to samo od nowa, wynik nie byłby sprawdzony przez człowieka, a plik mógłby się różnić między pobraniami.

## Do zrobienia przed wersją publiczną

* Hosting: GPU w chmurze uruchamiane tylko na czas separacji (np. kolejka + worker), pliki w magazynie obiektowym (S3/R2), Postgres zamiast SQLite.
* Potwierdzenie adresu e-mail, reset hasła, limity zapytań, ochrona przed spamem w społeczności.
* Regulamin, polityka prywatności, wzór karty prawnej – prawnik (szkice w `/strona/...`).
* Audyt WCAG 2.2 AA; opis tekstowy zapisu nutowego.
* Własna digitalizacja lub zgoda archiwów na redystrybucję plików (patrz pytania w `docs/`).
