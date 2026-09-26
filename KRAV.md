# Offline fakturaprogram for gård

## Omfang

Python og SQLite, én lokal bruker og noen få fakturaer per måned.
Kunderegister, prisliste, MVA per linje, logo, faktura som PDF og
betalingsregistrering/påminnelser. PDF lagres som BLOB sammen med
strukturerte fakturadata. Utsending skjer manuelt i e-postprogrammet.

## Plattform og grensesnitt

Brukerkrav: støtte både Zorin OS (Linux) og Windows fra samme Python-kode.
Anbefalt GUI er Tkinter med ttk. Prioriter tydelige tabeller, søk,
tastaturnavigasjon, lesbare skrifter og god avstand mellom feltene.
Databaselogikk, beregninger og PDF-generering holdes adskilt fra GUI.

Distribusjon pakkes separat på Linux og Windows med PyInstaller.
Brukeren skal ikke måtte installere Python. Pakken kan være en mappe
med startfil og avhengigheter; én enkelt binærfil er ikke et krav.
Støttede OS-versjoner og prosessorarkitektur må avklares før utgivelse.
Oppstart, filvalg, PDF-åpning og sikkerhetskopi må verifiseres på begge
plattformene, inkludert skjermskalering og norske tegn.

Databasen plasseres i en skrivbar datamappe adskilt fra programfilene.
Samme databaseformat brukes på begge plattformer. Backup/gjenoppretting
skal støtte flytting mellom maskiner. Uavhengige kopier synkroniseres
ikke automatisk; fakturering må skje fra én autoritativ database for
å unngå doble fakturanumre.

## Fakturautseende

Det vedlagte bildet av dagens papirfaktura er visuell referanse.
Behold tydelig avsender, mottaker, fakturanummer, dato, forfall,
kontonummer, varelinjer og summer. Ny PDF lages i A4 med valgfri logo,
lesbar tekst og støtte for flere sider. Betalingsinformasjon samles
tydelig; gammelt girofelt og systemleverandørens merke trengs ikke.
PDF-oppsettet er uavhengig av GUI-valget.

Eksempelets fakturanummer er 2026008, mens ønsket nytt format gir
20260008 for løpenummer 8. Ved overgang i samme år må nummerserien
starte etter siste utstedte løpenummer i gammelt system. Historiske
fakturaer beholder sine originale numre ved eventuell import.
Eksempelets MVA-behandling og rentetekst kopieres ikke automatisk;
disse må følge virksomhetens faktiske forhold og gjeldende regler.

## Kundekort

Undersøkt 26. september 2026. Fakturaen skal identifisere kjøper med
navn og adresse eller organisasjonsnummer. Dette er krav til
fakturainnhold; øvrige felt nedenfor er programvalg.

- Kundenummer: automatisk tildelt, unikt og ikke redigerbart.
- Kundetype: privatperson eller virksomhet.
- Navn: personens navn eller virksomhetens juridiske navn; påkrevd.
- Adresse: adresselinje 1 og 2, postnummer, poststed og land.
  Land har Norge som standard. Norske postnummer lagres som tekst.
- Organisasjonsnummer: valgfritt; kontroller format og kontrollsiffer
  for norske organisasjonsnumre når det fylles inn.
- Faktura-e-post: valgfritt for å lagre kunden, nødvendig for planlagt
  utsending på e-post. Vis tydelig om adressen mangler.
- Telefon og kontaktperson: valgfrie.
- Standard betalingsfrist i dager: arves fra gårdens innstillinger,
  kan overstyres på kunden og den enkelte faktura.
- Kundens referanse og eventuell separat leveringsadresse: valgfrie.
- Aktiv/inaktiv: historiske kunder beholdes selv om de ikke lenger brukes.

Ved ferdigstilling kreves navn og enten fullstendig adresse eller
organisasjonsnummer. Fullstendig adresse betyr adresselinje 1,
postnummer, poststed og land; adressevalidering må kunne tilpasses
utenlandske adresser. Fødselsnummer inngår ikke i kundekortet.
Kontaktperson eller e-postmottaker erstatter ikke kjøperens navn.
Leveringsdato og leveringssted registreres på fakturaen, med eventuell
leveringsadresse på kunden som forslag.

## Kundenummer

Foreløpig standard: 1, 2, 3 osv., uten årlig nullstilling.
Nummer tildeles når kunden lagres første gang, i en databasetransaksjon.
Numre til tidligere kunder gjenbrukes ikke.

## Fakturanummer

Brukerkrav: årstall etterfulgt av løpenummer, med ny serie hvert år.
Året følger fakturadatoen. Nummer lagres som tekst; internt lagres
også år og et numerisk sekvensnummer for entydig sortering.

Tolking av bokstavovergangen:

| Sekvensnummer | Fakturanummer i 2026 |
| --- | --- |
| 1 | 20260001 |
| 9999 | 20269999 |
| 10000 | 2026A000 |
| 10001 | 2026A001 |
| 10999 | 2026A999 |
| 11000 | 2026B000 |
| 35999 | 2026Z999 |
| 36000 | 2026AA000 |

Etter Z brukes AA, AB osv.; dette er en foreløpig utvidelse av
brukerens format. Årsserien starter igjen med 0001 neste år.
Nummer tildeles automatisk kun ved ferdigstilling. Kladd har ingen
fakturanummer. Tildeling, låsing og PDF-arkivering utføres samlet
i én transaksjon. Unikhetskrav på fakturanummer og (år, sekvensnummer)
hindrer duplikater. Feil ved ferdigstilling må ikke gi en delvis
utstedt faktura. Utstedte numre gjenbrukes ikke.

## Historikk og dokumenter

Ferdigstilte fakturaer lagrer kopier av kjøper- og selgeropplysninger,
linjetekster, priser og MVA. Senere registerendringer påvirker ikke
fakturaen eller PDF-en. Fakturainnhold og original PDF låses.
Betalinger, utsendingstidspunkt og påminnelser registreres separat.
Rettelser skjer med kreditnota med referanse til originalen og ved
behov ny faktura. En eksisterende faktura kan kopieres til ny kladd.
PDF kan åpnes, eksporteres og sendes på nytt.

## Kilder

- Python, ttk:
  https://docs.python.org/3/library/tkinter.ttk.html
- PyInstaller, pakking per operativsystem:
  https://pyinstaller.org/en/latest/usage.html
- Altinn, faktura (oppdatert 18. mars 2026):
  https://info.altinn.no/starte-og-drive/regnskap-og-revisjon/regnskap/faktura-salgsdokumentasjon/
- Skatteetaten, angivelse av kjøper i salgsdokumentet:
  https://www.skatteetaten.no/rettskilder/type/uttalelser/prinsipputtalelser/angivelse-av-kjoper-i-salgsdokumentet/
