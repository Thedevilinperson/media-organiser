# Collectiekaart — Mediabeheerder

Een webapplicatie voor het beheren van je collectie boeken, strips, comics, manga, anime, cd's en dvd's. Draait standalone op Windows óf binnen Home Assistant, en is bruikbaar op een smartphone.

## Wat zit erin

- **Basisweergave**: tabel met alle media, cascaderende filters (type, eigenaar, reeks, titel), een zoekbalk die over alle kolommen zoekt, en het totaal aantal per mediatype bovenaan. Op een smartphone wordt de tabel automatisch een kaartenlijst. Strips worden alfabetisch op reeks en dan op nummer gesorteerd.
- **Drie manieren van ingave**: volledig manueel, via barcode scannen (camera van je telefoon), of via een foto van de kaft.
- **Reeksanalyse**: toont ontbrekende nummers binnen je eigen collectie (lokaal berekend, geen internet nodig), plus een knop om best-effort te controleren of er nieuwe nummers zijn via De Poort.
- **Waarde van de collectie**: overzichtstabel per mediatype, met een best-effort schatting via Lastdodo per item.
- **Uitleenmodule**: registreer wie iets leent en wanneer; na 1 maand verschijnt een waarschuwing in de app en (indien geconfigureerd) een pushmelding in Home Assistant.
- **Instellingen**: eigenaars beheren, mediatypes toevoegen/verwijderen, AI API-sleutel instellen, Home Assistant-koppeling instellen, massa-import via Excel.

## Eerlijke kanttekeningen bij een paar vereisten

Twee punten uit de vereisten vragen om functionaliteit die afhangt van externe websites of AI, en verdienen een woordje uitleg:

1. **Foto-analyse zonder AI**: dit is onderzocht. Zonder AI is er geen betrouwbare manier om een willekeurige stripkaft te herkennen (titel, reeks én nummer tegelijk) — wél is het mogelijk om de tekst op de kaft te lezen met lokale OCR (tesseract, al ingebouwd, geen internet nodig). Dat levert een ruwe gok op (meestal de titel) die je dan manueel corrigeert. Voor betrouwbaardere, volautomatische herkenning van alle velden is een vision-model nodig — vandaar de optionele AI API-sleutel in Instellingen, die ook naar een **lokaal draaiend LLM** kan wijzen als je zelf geen data naar een externe API wil sturen (pas hiervoor `lookups.py` → `analyze_cover_ai` se `base_url` aan).

2. **Controle op nieuwe/ontbrekende nummers via De Poort**: dit gebeurt via webscraping (géén AI), en is dus gratis en lokaal. Het is wel **best-effort**: als De Poort de opbouw van hun website wijzigt, moet `series_analysis.py` → `parse_depoort_series` bijgewerkt worden. Dezelfde kanttekening geldt voor de Lastdodo-waardebepaling. Beide functies falen "zacht" (nette foutmelding in de app) als de site niet bereikbaar is, zodat de rest van de applicatie gewoon blijft werken.

## Standalone draaien op Windows

1. Zorg dat [Python 3.10 of nieuwer](https://www.python.org/downloads/) geïnstalleerd is (vink bij installatie "Add python.exe to PATH" aan).
2. Pak deze map ergens uit, bv. `C:\MediaBeheer`.
3. Dubbelklik op **`start_windows.bat`**. De eerste keer worden automatisch de benodigde onderdelen geïnstalleerd; dat kan een minuutje duren.
4. Zodra je "Mediabeheerder start op http://localhost:8099" ziet, open je die link in je browser.
5. Om de applicatie ook vanaf je telefoon te gebruiken (bv. om de barcode-scanner te gebruiken), open je op je telefoon `http://<IP-adres-van-je-pc>:8099`, zolang telefoon en pc op hetzelfde wifi-netwerk zitten. Een camera vereist meestal een beveiligde verbinding (https) of "localhost" — werkt het scannen niet via het gewone IP-adres, gebruik dan een lokale reverse proxy met een zelfondertekend certificaat, of test de scanfunctie via `http://localhost:8099` op de pc zelf met een aangesloten webcam.

Optioneel voor lokale OCR (foto-ingave zonder AI): installeer [Tesseract OCR voor Windows](https://github.com/UB-Mannheim/tesseract/wiki) en zorg dat het aan het systeem-PATH toegevoegd is. Zonder Tesseract werkt de rest van de applicatie gewoon door; enkel de OCR-foto-herkenning valt dan terug op een foutmelding totdat je een AI-sleutel instelt of Tesseract installeert.

## Draaien binnen Home Assistant

Er zijn twee manieren, van eenvoudig naar meer geïntegreerd:

### Optie A — snelst: als losse Docker-container naast Home Assistant
Als je Home Assistant OS of Supervised draait (of gewoon Docker op dezelfde machine):
```bash
docker build -t collectiekaart .
docker run -d --name collectiekaart -p 8099:8099 -v collectiekaart_data:/app/data -v collectiekaart_uploads:/app/static/uploads collectiekaart
```
Voeg daarna in Home Assistant een **Webpage-kaart** (of iframe-panel) toe die verwijst naar `http://<host-ip>:8099` — zo krijg je de mediabeheerder gewoon in je Lovelace-dashboard te zien.

### Optie B — als Home Assistant add-on
De map bevat een `config.yaml` en `Dockerfile` in het formaat van een HA add-on repository.
1. Zet deze map in een eigen git-repository.
2. Voeg die repository toe via **Instellingen → Add-ons → Add-on Store → ⋮ → Repositories**.
3. Installeer "Collectiekaart Mediabeheerder" en start hem op.

**Kanttekening bij Ingress**: het add-on manifest schakelt Home Assistant's Ingress in (zodat de app binnen de HA-interface zelf verschijnt, zonder apart poortbeheer). Deze Flask-applicatie is niet expliciet getest achter een Ingress-subpad; werkt het menu of laden van afbeeldingen niet correct via Ingress, zet dan in `config.yaml` `ingress: false` en gebruik in plaats daarvan poort 8099 rechtstreeks (zoals bij Optie A) — dat werkt sowieso.

De uitleen-waarschuwingen naar Home Assistant (zie Instellingen) gebruiken de gewone Home Assistant REST API en werken in beide gevallen (add-on of losse container), zolang je in Instellingen de juiste HA-URL en een Long-Lived Access Token invult.

## Massa-import via Excel

Ga naar **Instellingen → Massa-import**. Verwachte kolomnamen (hoofdletterongevoelig, Nederlands of Engels): `type, titel, reeks, nummer in de reeks, auteur, collectie, nummer in de collectie, nummer van de druk, eigenaar, dubbel, hardcover, staat, commentaar, muzikant, jaar, taal audio, taal ondertiteling, barcode, waarde`. De kolom `type` moet de interne code van een bestaand mediatype bevatten (zichtbaar in Instellingen, bv. `strip`, `boek`, `cd`, `dvd`); onbekende types worden overgeslagen en gemeld na import.

## Mediatypes en velden aanpassen

In **Instellingen** kan je nieuwe mediatypes toevoegen (bv. "Bordspel") en kiezen welk "veldenprofiel" ze gebruiken (strip/boek/cd/dvd/vrij) — dat bepaalt welke extra invulvelden op het toevoegformulier verschijnen.

## Technisch

- Python/Flask, SQLite-databank (bestand `data/mediabeheer.db`), geen externe databaseserver nodig.
- Geüploade kaftfoto's komen in `static/uploads/`.
- Een achtergrondtaak (APScheduler) controleert dagelijks op te lang uitgeleende media.
