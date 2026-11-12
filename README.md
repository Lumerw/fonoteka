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

Adres: https://fonoteka.teraz-platforma.workers.dev (domyślna domena Cloudflare; własną domenę podpinamy później w panelu Cloudflare → Workers → fonoteka → Domains).

```bash
.venv/bin/python app/export_static.py      # buduje dist/ (PL, /en, /uk)
npx wrangler deploy                        # konfiguracja w wrangler.jsonc
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
