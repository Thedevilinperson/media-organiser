# Wijzigingen

## 0.1.5

- Het invulformulier reageerde na een update niet meer op een wisseling van
  type. De oorzaak lag niet in de code van het formulier zelf: de URL's van de
  stylesheet en de scripts droegen geen versienummer, waardoor een browser na
  een update het opgeslagen script van de vorige versie bleef gebruiken. Dat
  oude script zocht naar markeringen die in het nieuwe formulier niet meer
  bestaan, zodat er niets meer getoond of verborgen werd. Elke verwijzing naar
  een statisch bestand draagt nu het versienummer.
- "Velden per type" in Instellingen staat nu in een tabel met de vinkjes netjes
  onder elkaar in twee kolommen.

## 0.1.4

- Het voorbeeldbestand voor de massa-import is te downloaden vanuit Instellingen.
  Het wordt bij het opvragen opgebouwd uit dezelfde kolomtabel als de importer,
  met een tweede blad met uitleg.
- Het invulformulier toont voortaan alleen de velden die bij het gekozen type
  horen. Velden als staat, barcode en waarde stonden er eerder bij elk type,
  ook waar ze niet thuishoorden.
- Nieuw blok "Velden per type" in Instellingen: per mediatype zie je elk veld en
  stel je in of het getoond wordt en of het verplicht is. Verplichte velden
  worden ook op de server gecontroleerd.
- Een verborgen veld wist niets: bestaande waarden blijven bewaard en blijven
  zichtbaar op de volledige lijst.
- Bestaande databanken worden bij het opstarten aangevuld met de nieuwe kolommen,
  zonder dat er gegevens verloren gaan.

## 0.1.3

- Het overzicht is opnieuw opgebouwd: per mediatype een korte tabel met alleen de
  kolommen die voor dat type nuttig zijn, en alleen nog een zoekbalk. Op een
  telefoon zie je zo meteen resultaten in plaats van eerst vier keuzelijsten.
- Nieuwe pagina "Volledige lijst" tussen Overzicht en Toevoegen, met alle velden
  en de cascaderende filters die eerder op het overzicht stonden.
- Het overzicht blijft ook op een smal scherm een echte tabel; de volledige lijst
  wordt daar wel een kaartenlijst, omdat drieëntwintig kolommen anders onleesbaar
  zijn.

## 0.1.2

- Het veld "Staat" stond alleen bij strips en verscheen dus niet bij een boek.
  Het staat nu bij elk type in het algemene deel van het formulier.
- Een knop "Zoek richtprijs" op het invulformulier zelf, die werkt op titel en
  reeks en dus ook bij een item dat nog niet opgeslagen is.
- Op de waardepagina kan je de waarde per rij rechtstreeks invullen en bewaren,
  zonder het item te openen.
- LastDodo blokkeert geautomatiseerde aanvragen en gaf daardoor een 403. De app
  meldt dat nu in gewone taal en toont een zoeklink naar hun zoekpagina in plaats
  van een technische foutmelding.

## 0.1.1 — scanner

- De camera startte niet op Android. De ingebouwde barcodelezer van de browser
  kreeg het formaat `isbn` mee, dat niet bestaat; daardoor faalde het aanmaken van
  de lezer meteen. De app vraagt nu eerst op welke formaten het toestel
  ondersteunt en valt terug op de bibliotheek als er geen bruikbare overblijven.
- Verkeerd gelezen barcodes. EAN-8 en Code 128 stonden aan, waardoor de halve
  streepjescode van een boek als geldige EAN-8 gelezen kon worden: 9789023467588
  werd 17896016. Alleen EAN-13 en UPC-A worden nog aanvaard, het controlecijfer
  wordt nagerekend, en een code telt pas als hij twee keer hetzelfde gelezen wordt.
- Een invoerveld om de cijfers onder de barcode zelf in te typen.
- Duidelijke meldingen wanneer de camera geweigerd, bezet of afwezig is.
- De opzoeking raadpleegt nu Google Books en Open Library samen in plaats van na
  elkaar, wat Nederlandstalige uitgaven vaker vindt.

## 0.1 — eerste versie

Eerste werkende versie, opgebouwd volgens de vereisten.

- Overzicht met zoekbalk over alle kolommen, cascaderende filters op type,
  eigenaar, reeks en titel, aantallen per type bovenaan, en een tabel die op een
  smartphone een kaartenlijst wordt.
- Ingave op drie manieren: manueel, via een barcode en via een foto van de kaft.
- Reeksanalyse met lokaal berekende gaten en een controle op nieuwere nummers bij
  De Poort.
- Waarde per type, met een richtprijs per item via Lastdodo.
- Uitleenmodule met een melding naar Home Assistant na dertig dagen.
- Instellingen voor eigenaars, types media, eigen velden, koppelingen en
  massa-import uit Excel.
- Handleiding in de applicatie zelf.
- Screening op kwetsbaarheden, zie SECURITY.md.

Werkt achter Home Assistant Ingress: de app leest het subpad uit de header
`X-Ingress-Path` en bouwt haar links daarmee op.
