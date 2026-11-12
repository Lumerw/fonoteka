# Fonoteka – UX panelu użytkownika i społeczności (prototyp)

## Zasada
Konto jest bezpłatne i nie jest barierą: katalog, odsłuch, mikser stemów i karty prawne działają bez logowania. Logowanie jest potrzebne tylko tam, gdzie daje użytkownikowi coś w zamian: pobranie z potwierdzeniem statusu, separator, bibliotekę i społeczność.

## Panel („Mój panel”)
Jedna strona z kotwicami zamiast wielu podstron – łatwa nawigacja klawiaturą i czytnikiem ekranu.

| Sekcja | Po co | Co zawiera |
|---|---|---|
| Moja biblioteka | szybki powrót do utworów, z którymi pracuję | zapisane utwory z odtwarzaczem i linkiem do karty |
| Historia pobrań | dowód legalnego źródła przy wydaniu utworu | data, plik, wersja karty prawnej, link do **potwierdzenia pobrania** (do druku/PDF, z sumą SHA-256) |
| Moje separacje | wyniki separatora | status, termin usunięcia (24 h), link do wyników |
| Moja aktywność | moje wpisy i odpowiedzi | wpisy z liczbą odpowiedzi |
| Ustawienia | RODO i preferencje | imię, profil (kompozytor, archiwista…), język, eksport danych JSON, usunięcie konta |

Puste stany zawsze mówią, co zrobić dalej (np. „Zapisuj utwory przyciskiem…” + link do katalogu).

## Społeczność – cztery rodzaje wpisów
Zamiast ogólnego forum: wpisy mają typ, bo każdy typ ma inną ścieżkę obsługi.

1. **Projekt** – „pokaż, co stworzyłeś” (link do utworu, który powstał z nagrań). Buduje dowód wpływu do raportu z grantu.
2. **Pytanie** – pytania o użycie materiałów, technikę, prawo.
3. **Poprawka opisu** – zgłoszenie błędu w metadanych, przypięte do utworu (crowdsourcing jak w Europeanie); trafia do muzykologa.
4. **Zbiór płyt** – kolekcjonerzy i archiwa zgłaszają nagrania do digitalizacji; zasila katalog po grancie.

Wpis może być przypięty do utworu – wtedy pojawia się na stronie utworu („Społeczność o tym utworze”). Moderacja: administrator ukrywa wpis. Zasady wyświetlane nad formularzem.

## Następne kroki (po prototypie)
- Kolekcje (własne listy utworów, np. „tanga do spektaklu”), udostępniane linkiem.
- Powiadomienia e-mail o odpowiedziach i o zmianie karty prawnej pobranego utworu (nowa wersja karty → informacja dla osób, które pobrały plik).
- Profil publiczny twórcy z jego projektami.
- Zgłaszanie wpisów do moderacji przez użytkowników.
