# Screening op kwetsbaarheden — Collectiekaart 0.1

Vereiste 3a vraagt om een screening van de code. Hieronder staat wat er bij het
doorlichten van de eerste opzet naar boven kwam, en wat er in 0.1 mee gebeurd is.
De applicatie draait in een thuisnetwerk zonder aanmelding: het uitgangspunt is
dat iedereen die de pagina kan openen, alles mag. De risico's zitten dus vooral
bij gegevens die van buitenaf binnenkomen (formulieren, uploads, externe
websites) en bij het lekken van geheimen.

## Bevindingen en oplossingen

**B1 — Vaste sleutel in de broncode (hoog).**
De sessiesleutel stond hardgecodeerd als `"dev-key-verander-mij"`. Wie de code
kent, kan daarmee sessiecookies vervalsen. Nu wordt de sleutel bij de eerste
start willekeurig aangemaakt en bewaard in `data/secret.key` met rechten 600, of
overgenomen uit de omgevingsvariabele `SECRET_KEY`. Zie `config.py`.

**B2 — Geheimen teruggestuurd naar de browser (hoog).**
De pagina Instellingen zette de AI-sleutel en het Home Assistant-token letterlijk
in de HTML, ook al stond het veld op `type="password"`. Iedereen die de pagina
bekijkt of de broncode opent, las ze zo mee. Nu stuurt de server alleen terug of
een geheim ingevuld is; wissen doe je met een expliciet aankruisvakje.
Zie `views/settings.py`.

**B3 — Geen CSRF-bescherming (hoog).**
Elk POST-formulier kon door een willekeurige andere website afgevuurd worden,
inclusief verwijderen en importeren. Elk formulier bevat nu een token dat aan de
sessie gekoppeld is; `security.py` controleert dat bij elke POST met een
tijdsconstante vergelijking. Ook de fetch-aanroepen sturen het token mee.

**B4 — XSS via gegevens van externe websites (hoog).**
`scan.html` en `series_analysis.html` zetten antwoorden van externe bronnen met
`innerHTML` op de pagina. Een gemanipuleerd antwoord kon zo scripts uitvoeren.
Alle JavaScript staat nu in aparte bestanden en bouwt de weergave op met
`textContent` en `createElement`. Daarbovenop stuurt de server een
Content-Security-Policy mee die inline scripts blokkeert.

**B5 — Ongefilterde velden uit een AI-antwoord (middel).**
Het resultaat van de foto-analyse ging ongefilterd als `**fields` naar `url_for`.
Een antwoord met onverwachte sleutels kon daardoor het gedrag van de link sturen.
Zowel de barcode- als de AI-opzoeking laten nu enkel een vaste lijst van velden
door en kappen te lange waarden af. Zie `services/lookups.py`.

**B6 — Uploads werden niet gecontroleerd (middel).**
Alleen de bestandsnaam werd nagekeken. Een script met de naam `kaft.jpg` belandde
gewoon in de map met statische bestanden. Nu wordt elke upload met Pillow geopend
en gecontroleerd, krijgt hij een nieuwe willekeurige naam, en staan de bestanden
buiten de statische map. Ze worden uitgeserveerd via `send_from_directory`, dat
padmanipulatie zoals `../../` blokkeert. De uploadlimiet ging van 16 MB naar 8 MB.

**B7 — Technische foutmeldingen naar de browser (middel).**
Ongeldige invoer, bijvoorbeeld letters in een nummerveld, veroorzaakte een
onbehandelde `ValueError` en daarmee een stacktrace. Alle invoer loopt nu langs
`safe_int`, `safe_float` en `clean_text`, en een onverwachte fout geeft een nette
pagina; de details gaan naar het logboek.

**B8 — Vertrouwen op JavaScript voor gegevensintegriteit (laag).**
Het jaartal van een dvd werd door JavaScript in een ander veld gekopieerd voor
het versturen. Met JavaScript uitgeschakeld ging dat mis. Dat is opgelost door
één jaarveld te gebruiken; de server bepaalt de betekenis, niet de browser.

**B9 — Ontwikkelserver als productieserver (laag).**
De ingebouwde Flask-server waarschuwt daar zelf voor in het logboek. De app
gebruikt nu waitress wanneer die beschikbaar is, en valt anders terug.

**B10 — Verwijderen zonder controle op gebruik (laag).**
Een eigenaar of mediatype verwijderen liet items achter met een verbroken
verwijzing. Verwijderen wordt nu geweigerd zolang er items aan hangen.

## Wat bewust niet is opgelost

- **Geen aanmelding.** De app is bedoeld voor een eigen netwerk of achter de
  aanmelding van Home Assistant. Wil je haar toch op het internet zetten, plaats
  er dan een reverse proxy met authenticatie voor.
- **Scraping blijft broos.** De aanroepen naar De Poort en Lastdodo lezen HTML
  van een website die kan wijzigen. Dat is geen beveiligingsprobleem, maar
  verklaart wel waarom die functies soms niets vinden. Ze falen zacht.
- **SQLite zonder versleuteling.** Het databankbestand staat onversleuteld op je
  eigen toestel, net als je fotomap. Bescherm die map zoals je andere
  persoonlijke bestanden beschermt.

## Verstuurde beveiligingsheaders

`Content-Security-Policy` (geen inline scripts, geen externe bronnen behalve de
scannerbibliotheek), `X-Content-Type-Options: nosniff` en
`Referrer-Policy: same-origin`. `frame-ancestors` wordt bewust niet beperkt,
anders kan Home Assistant de app niet in een kader tonen.
