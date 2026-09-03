# Collectiekaart 0.1

Een webapplicatie om je collectie boeken, strips, comics, manga, anime, cd's en
dvd's bij te houden. Draait standalone op Windows of als add-on in Home
Assistant, en is bruikbaar op een smartphone.

## Wat er in zit

- **Overzicht** met een zoekbalk die over alle kolommen tegelijk zoekt, en vier
  keuzelijsten (type, eigenaar, reeks, titel) die elkaars inhoud beperken tot wat
  nog mogelijk is. Bovenaan staan de aantallen per type. Strips, comics, manga en
  anime staan alfabetisch op reeks en daarbinnen op nummer. Op een telefoon wordt
  de tabel een kaartenlijst.
- **Drie manieren van ingeven**: manueel, met de camera via een barcode, of door
  een foto van de kaft te laten analyseren.
- **Reeksanalyse**: welke nummers ontbreken in je reeksen, en zijn er nummers
  verschenen die je nog niet hebt.
- **Waarde**: totaal per type, met een richtprijs per item via Lastdodo.
- **Uitleen**: wie leende wat en sinds wanneer, met een melding in Home Assistant
  na dertig dagen.
- **Instellingen**: eigenaars, types media, eigen velden, AI-sleutel, de
  koppeling met Home Assistant en massa-import uit Excel.
- **Handleiding** in de applicatie zelf, onder "Handleiding" in het menu.

## Twee vereisten die uitleg verdienen

**Een foto analyseren zonder AI.** Dit is uitgezocht. Een willekeurige kaft
volledig herkennen, dus titel én reeks én nummer tegelijk, lukt niet betrouwbaar
zonder beeldmodel. Wat wél lukt zonder AI en zonder internet is de tekst op de
kaft lezen met Tesseract; dat zit ingebouwd en levert een ruwe gok op die je zelf
corrigeert. Wil je meer, dan is er de optionele AI-sleutel bij Instellingen. Die
mag ook naar een LLM wijzen die je zelf thuis draait: vul bij "Eigen AI-adres"
het adres van je eigen model in en er verlaat niets je netwerk.

**Nieuwe nummers opsporen via De Poort.** Dit gebeurt door hun zoekpagina uit te
lezen, dus zonder AI, gratis en vanaf je eigen toestel. Het is wel afhankelijk
van de opbouw van hun website: wijzigt die, dan moet
`services/series_analysis.py` bijgewerkt worden. Hetzelfde geldt voor Lastdodo in
`services/value_estimation.py`. Beide functies falen zacht, met een nette melding
in de app, zodat de rest gewoon blijft werken.

## Standalone op Windows

1. Installeer [Python 3.10 of nieuwer](https://www.python.org/downloads/) en vink
   bij de installatie "Add python.exe to PATH" aan.
2. Pak deze map uit, bijvoorbeeld naar `C:\Collectiekaart`.
3. Dubbelklik op **`start_windows.bat`**. De eerste keer duurt dat een minuutje.
4. Open <http://localhost:8099> in je browser.

Wil je de app ook op je telefoon gebruiken, surf dan naar
`http://<ip-van-je-pc>:8099` zolang telefoon en pc op hetzelfde wifi zitten. De
camera werkt daar niet: browsers geven alleen toegang tot de camera over https of
op localhost. Voor het scannen gebruik je dus best de Home Assistant-installatie
hieronder, of je typt de barcode zelf in.

Voor de lokale tekstherkenning installeer je
[Tesseract OCR voor Windows](https://github.com/UB-Mannheim/tesseract/wiki) en
zet je het in het PATH. Zonder Tesseract werkt de rest gewoon door.

## In Home Assistant

### Als add-on (aanbevolen)

De map hierboven is opgebouwd als een add-on-repository: `repository.yaml` in de
hoofdmap en de add-on zelf in de submap `collectiekaart`.

1. Zet de volledige map in een eigen git-repository.
2. In Home Assistant: **Instellingen → Add-ons → Add-on Store → ⋮ → Repositories**
   en plak de URL van je repository.
3. Installeer "Collectiekaart" en start de add-on.

De app verschijnt dan in het menu van Home Assistant zelf, via Ingress. De
databank en de kaftfoto's komen in `/data` terecht en overleven een herstart en
een update.

Deze versie werkt achter Ingress: de app leest het subpad uit de header
`X-Ingress-Path` en bouwt haar links daarmee op. Zag je in een eerdere versie een
pagina zonder opmaak met links die een foutmelding gaven, dan was dat precies dit
probleem.

### Als losse container

```bash
docker build -t collectiekaart .
docker run -d --name collectiekaart -p 8099:8099 \
  -v collectiekaart_data:/data collectiekaart
```

Voeg daarna in Home Assistant een Webpage-kaart toe die naar
`http://<host-ip>:8099` verwijst.

De meldingen over uitleningen werken in beide gevallen, zolang je bij
Instellingen het adres van Home Assistant en een Long-Lived Access Token invult.

## Massa-import uit Excel

Ga naar **Instellingen → Massa-import**. Herkende kolomnamen, in het Nederlands
of het Engels en hoofdletterongevoelig: `type, titel, reeks, nummer in de reeks,
auteur, collectie, nummer in de collectie, nummer van de druk, eigenaar, dubbel,
hardcover, staat, commentaar, muzikant, jaar, taal audio, taal ondertiteling,
barcode, waarde`. In `voorbeeld_import.xlsx` staat een ingevuld voorbeeld.

De kolom `type` bevat de interne code van een bestaand type, bijvoorbeeld `strip`
of `boek`. Rijen met een onbekend type worden overgeslagen en na afloop opgesomd.
Eigenaars die nog niet bestaan, worden automatisch aangemaakt.

## Mappenstructuur

```
collectiekaart_v0.1/
├── repository.yaml              add-on-repository voor Home Assistant
└── collectiekaart/
    ├── app.py                   applicatiefabriek en opstart
    ├── config.py                paden, sleutel, limieten
    ├── middleware.py            ondersteuning voor Home Assistant Ingress
    ├── security.py              CSRF, headers, invoervalidatie
    ├── models.py                databankmodellen
    ├── extensions.py            gedeelde extensies
    ├── version.py               versienummer
    ├── views/                   één module per scherm
    │   ├── main.py              overzicht, handleiding, kaftfoto's
    │   ├── main_helpers.py      zoeken, filteren, sorteren
    │   ├── media.py             toevoegen, wijzigen, scannen, foto
    │   ├── analysis.py          reeksen en waarde
    │   ├── lending.py           uitleen
    │   └── settings.py          instellingen en import
    ├── services/                logica en externe koppelingen
    │   ├── lookups.py           barcode en foto-analyse
    │   ├── series_analysis.py   ontbrekende en nieuwe nummers
    │   ├── value_estimation.py  richtprijs
    │   ├── importer.py          Excel-import
    │   ├── ha_integration.py    Home Assistant
    │   ├── images.py            kaftfoto's verkleinen
    │   └── jobs.py              dagelijkse controle
    ├── templates/               schermen
    ├── static/css, static/js    opmaak en scripts
    ├── data/                    databank (wordt aangemaakt)
    └── uploads/                 kaftfoto's (worden aangemaakt)
```

## Technisch

- Python met Flask en SQLite. Eén bestand, geen databaseserver.
- Bewust geen pandas en geen externe lettertypes: dat scheelt geheugen,
  installatietijd op een Raspberry Pi en een handvol netwerkaanvragen per pagina.
  Kaftfoto's worden bij het opslaan verkleind tot 900 pixels.
- Het overzicht haalt zijn gegevens in één query op met eager loading, in plaats
  van een aparte query per rij.
- Een achtergrondtaak controleert één keer per dag op te lang uitgeleende media.
- Zie `SECURITY.md` voor de screening op kwetsbaarheden.

## Back-up

Kopieer de map `data` (standalone) of `/data` van de add-on. Daar zitten de
databank, de kaftfoto's en de sessiesleutel.
