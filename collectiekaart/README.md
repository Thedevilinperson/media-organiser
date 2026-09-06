# Collectiekaart 0.1

Een webapplicatie om je collectie boeken, strips, comics, manga, anime, cd's en
dvd's bij te houden. Draait standalone op Windows of als add-on in Home
Assistant, en is bruikbaar op een smartphone.

## Wat er in zit

- **Overzicht**: een korte tabel per mediatype met alleen de kolommen die er voor
  dat type toe doen. Strips op reeks, nummer en titel; boeken op auteur en titel;
  cd's op muzikant, titel en jaar; dvd's op titel en jaar. Bovenaan de aantallen
  per type, daaronder één zoekbalk die over alle kolommen zoekt. Blijft ook op een
  smartphone een echte tabel.
- **Volledige lijst**: dezelfde collectie met álle velden, inclusief je eigen
  velden, plus de vier keuzelijsten (type, eigenaar, reeks, titel) die elkaars
  inhoud beperken tot wat nog mogelijk is, en de knoppen om te wijzigen of te
  verwijderen.
- **Vier manieren van ingeven**: manueel, met de camera via een barcode, door een
  foto van de kaft te laten analyseren, of door te vertrekken van een item dat je
  al hebt ("Overnemen" en "Volgend deel").
- **Reeksanalyse**: welke nummers ontbreken in je reeksen, en zijn er nummers
  verschenen die je nog niet hebt.
- **Waarde**: totaal per type, met een waarde die je per item meteen kan invullen en een poging
  tot richtprijs via LastDodo.
- **Uitleen**: wie leende wat en sinds wanneer, met een melding in Home Assistant
  na dertig dagen.
- **Instellingen**: eigenaars, types media, eigen velden, en per mediatype welke
  velden op het formulier verschijnen en welke verplicht zijn. Verder de
  AI-sleutel, de koppeling met Home Assistant en de massa-import uit Excel, met
  een voorbeeldbestand om te downloaden.
- **Handleiding** in de applicatie zelf, onder "Handleiding" in het menu.

## Twee vereisten die uitleg verdienen

**Een foto analyseren zonder AI.** Dit is uitgezocht. Een willekeurige kaft
volledig herkennen, dus titel én reeks én nummer tegelijk, lukt niet betrouwbaar
zonder beeldmodel. Wat wél lukt zonder AI en zonder internet is de tekst op de
kaft lezen met Tesseract; dat zit ingebouwd en levert een ruwe gok op die je zelf
corrigeert. Wil je meer, dan is er de optionele AI-sleutel bij Instellingen. Die
mag ook naar een LLM wijzen die je zelf thuis draait: vul bij "Eigen AI-adres"
het adres van je eigen model in en er verlaat niets je netwerk.

**Een barcode opzoeken.** Zeven catalogi worden parallel bevraagd, allemaal
gratis en zonder sleutel: Google Books, Open Library, de Koninklijke Bibliotheek
(GGC, via SRU), Wikidata, de Bibliothèque nationale de France, openBD en
MusicBrainz. Elk dekt een ander gat. De KB is de Nederlandse nationale
bibliografie en beschrijft zowat elke uitgave die hier met een ISBN verscheen,
stripalbums inbegrepen; Wikidata is de enige bron die bij een stripalbum vaak
reeks én nummer kent; MusicBrainz vangt de EAN-codes van cd's en dvd's op, die in
geen enkele boekencatalogus staan. Bij Google Books wordt uitdrukkelijk een land
meegegeven, anders weigert die API een aanvraag die van een server komt. Wat er
dan nog ontbreekt, wordt aangevuld vanuit je eigen collectie: herkent de app een
reeks die je al hebt in de gevonden titel, dan vult ze reeks, nummer, auteur en
collectie zelf in. Sites zonder open interface (Stripinfo, LastDodo,
Boekwinkeltjes) worden niet geschraapt; die geven een zoeklink. Details en de
volledige afweging staan in `services/barcode_sources.py`.

**Nieuwe nummers opsporen via De Poort.** Dit gebeurt door hun zoekpagina uit te
lezen, dus zonder AI, gratis en vanaf je eigen toestel. Het is wel afhankelijk
van de opbouw van hun website: wijzigt die, dan moet
`services/series_analysis.py` bijgewerkt worden. Voor LastDodo ligt het anders: die site beschermt zich actief tegen
geautomatiseerde aanvragen en antwoordt op een verzoek vanaf een server meestal
met een 403. Dat is een bewuste keuze van hen, geen storing, en er valt niet
omheen te werken zonder hun voorwaarden te schenden. De app doet één nette
poging en toont daarna een zoeklink naar LastDodo, zodat je de cataloguswaarde in
één klik zelf kan opzoeken en meteen in de lijst invullen. Beide functies falen
zacht, zodat de rest gewoon blijft werken.

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
barcode, waarde`. Met de knop "Voorbeeldbestand downloaden" haal je een ingevuld
voorbeeld op; dat wordt bij het downloaden opgebouwd uit dezelfde kolomtabel als
de importer gebruikt, zodat het nooit uit de pas loopt.

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
    │   ├── lookups.py           opzoeken bij barcode en foto-analyse
    │   ├── barcode_sources.py   de zeven catalogi achter het scannen
    │   ├── series_analysis.py   ontbrekende en nieuwe nummers
    │   ├── value_estimation.py  richtprijs
    │   ├── importer.py          Excel-import
    │   ├── sample_import.py     voorbeeldbestand voor de import
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
- De zeven barcodebronnen worden parallel bevraagd met een gezamenlijke
  tijdslimiet, en het resultaat wordt kort in het geheugen bewaard. Zeven
  catalogi na elkaar aanspreken duurt op een Raspberry Pi al snel een halve
  minuut; samen blijft het onder de vijftien seconden.
- Zie `SECURITY.md` voor de screening op kwetsbaarheden.

## Back-up

Kopieer de map `data` (standalone) of `/data` van de add-on. Daar zitten de
databank, de kaftfoto's en de sessiesleutel.
