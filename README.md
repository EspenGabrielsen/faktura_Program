# Gårdsfaktura

Et enkelt offline-program i Python, Tkinter/ttk og SQLite.
Koden er delt i tre filer:

- `app.py`: vinduer og knapper.
- `database.py`: lagring, fakturanummer og beløpsberegning.
- `invoice_pdf.py`: A4-PDF med ReportLab.

## Starte på Linux

Ferdige programpakker ligger i `dist/`. Pakk ut pakken i en fast mappe og
start `Gardsfaktura` på Linux eller `Gardsfaktura.exe` på Windows.
Disse trenger ikke en separat Python-installasjon. Pakken inneholder
`KOM-I-GANG.txt` og en fil som lager snarvei på skrivebordet.
Linux-pakken er bygget for Zorin OS 18 / Ubuntu 24.04 og x86-64.
Windows-pakken er bygget for Windows 10 eller nyere og x64.

For å kjøre kildekoden under utvikling:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Tkinter må være tilgjengelig i Python-installasjonen. På Zorin kan
pakken `python3-tk` installeres hvis den mangler.

## Starte på Windows

Installer Python med Tcl/Tk-støtte og kjør i PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

## Bruk

1. Fyll inn gårdens opplysninger under **Innstillinger**. Velg eventuelt logo.
2. Ved overgang fra gammelt system: sett siste brukte løpenummer for året
   før den første fakturaen ferdigstilles. Er det siste nummeret `2026008`,
   oppgi år `2026` og løpenummer `8`. Neste nummer blir `20260009`.
3. Legg inn kunder og eventuelt prisliste. Kundenummer tildeles automatisk.
4. Opprett en faktura. Priser oppgis eksklusive MVA; MVA-type velges per linje.
   Antall kan skrives med komma eller punktum. Datoer skrives `ÅÅÅÅ-MM-DD`.
5. Lagre kladd eller ferdigstill. Ferdigstilling låser fakturaen og lagrer PDF.
6. Eksporter PDF for manuell utsending, registrer innbetalinger og lag ved
   behov en betalingspåminnelse. Påminnelser har ikke gebyr eller rente.

Fakturalisten kan filtreres på status og år. **Ubetalte** inkluderer også
forfalte fakturaer. Søkefeltet søker på kundenavn eller fakturanummer og
kan kombineres med filtrene. Klikk på kolonneoverskriftene for å sortere;
klikk igjen for å snu rekkefølgen. Beløp og fakturanummer sorteres numerisk.
Velg en kladd og trykk **Slett kladd** for å fjerne den. Utstedte fakturaer
kan ikke slettes, og sletting av kladder bruker ikke opp fakturanumre.

Knappene er samlet i tre merkede grupper: **Faktura** (blå),
**PDF og utskrift** (lilla) og **Betaling og oppfølging** (grønn).
**Ny faktura** er fremhevet, og **Slett kladd** står separat i rødt.
Hold musepekeren over knapper som trenger forklaring i omtrent et halvt
sekund for å vise hjelpetekst. Dette gjelder også i popup-vinduene.
Hjelpen forsvinner når pekeren flyttes eller du klikker.

**Skriv ut kopi …** åpner den arkiverte fakturaen i PDF-leseren med
**KOPI** øverst på hver side. Velg **Skriv ut** (`Ctrl+P`) i PDF-leseren.
Originalen i databasen endres ikke. Alle nye programvinduer åpnes foran
foreldrevinduet; fakturalinjer åpnes foran fakturakladden.

Denne versjonen mangler kreditnota og PDF-forhåndsvisning av kladd.
Ikke ta den i ordinær bruk før kreditnota er på plass og fakturaoppsettet
er kontrollert for virksomheten. Windows-bygget og fakturatestene er
kjørt med Windows-Python i Wine; en fysisk Windows-PC er ikke testet.

## Data og sikkerhetskopi

På Linux lagres databasen normalt i
`~/.local/share/gardsfaktura/faktura.sqlite3`. På Windows brukes
`%LOCALAPPDATA%\Gardsfaktura\faktura.sqlite3`.

For å prøve programmet med lokale testdata:

```bash
python app.py --database data/test.sqlite3
```

**Sikkerhetskopi** kopierer hele databasen, inkludert logo og faktura-PDF-er.
Oppbevar gjerne en kopi på en annen disk. Ved gjenoppretting eller flytting:
lukk programmet på begge maskiner og kopier backupen til databasefilens
plassering. Bruk én oppdatert database om gangen; kopier synkroniseres ikke.
Ved **Åpne PDF** opprettes en midlertidig PDF-fil som systemets vanlige
PDF-leser åpner. Filen blir liggende i systemets midlertidige mappe.

## Kontrollere koden

```bash
.venv/bin/python -m unittest -v
```

Testene bruker egne databaser i minnet og endrer ikke lokale fakturadata.

Se `KRAV.md` for avtalte krav og kildehenvisninger.

## Bygge nye programpakker

Installer `requirements-build.txt` i et virtuelt miljø og kjør `python build.py`.
Det lager programfil, snarveiskript, lisenser, veiledning og en arkivpakke i
`dist/`. Bygg Linux-pakken på Linux og Windows-pakken med Windows-Python.
Windows-Python kan også kjøres i et separat Wine-miljø på Linux.
PyInstaller brukes slik det er beskrevet i
[dokumentasjonen](https://pyinstaller.org/en/stable/usage.html).
Zorin OS 18 har Ubuntu 24.04 som base, se
[Zorins tekniske detaljer](https://zorin.com/os/details/).
