# Wijzigingen

## 0.1.10

- De reeksenpagina had geen manier om meteen te zien welke reeksen aandacht
  nodig hebben zodra een collectie groot wordt. Er staat nu een vijfde filter
  "Status" bij de andere keuzelijsten, met vier opties: "Alles", "Ontbrekende
  nummers, geen nieuwe gevonden", "Ontbrekende nummers, mét nieuwe gevonden"
  en "Volledige reeks, mét nieuwe gevonden". Zo filter je in één klik op net
  die reeksen waar je nog iets voor moet doen, los van de bestaande filters op
  type, eigenaar, reeks en auteur. De kolom "Nieuw bij De Poort" met het
  resultaat van de controle op nieuwe exemplaren stond al op deze pagina en
  blijft ongewijzigd.

## 0.1.9

- De volledige lijst toonde altijd alle vierentwintig kolommen, ook velden die
  voor geen enkel getoond mediatype van toepassing zijn — bv. "Taal audio" en
  "Ondertiteling" bij een lijst zonder dvd's, of "Hardcover" en "Staat" bij een
  lijst met enkel cd's. De lijst toont nu enkel de kolommen die bij minstens
  één van de mediatypes in het huidige resultaat horen, gebaseerd op dezelfde
  instelling ("Velden per type" in Instellingen) die ook het invulformulier
  al gebruikte. Filter je op één type, dan valt de tabel meteen een stuk
  smaller uit; bij "Alles" blijft de unie van de aanwezige types te zien.
- Rijen op de volledige lijst konden drie regels hoog worden zodra een cel
  wat langere tekst bevatte (bv. een gedeelde eigenaar als "Gwen & Greet").
  Cellen staan nu standaard op één regel; de tabel schuift al horizontaal
  mee als ze breder wordt dan het scherm, dus er gaat niets verloren.

## 0.1.8

- Overzicht, Volledige lijst, Waarde, Uitleen en Reeksen gebruiken voortaan de
  volle breedte van het scherm in plaats van een vaste breedte van 1180px, en
  de rijen van een tabel staan dichter op elkaar. Op een breed scherm bleef
  daardoor voorheen veel ruimte onbenut, vooral zichtbaar bij de Volledige
  lijst met veel kolommen. Formulierpagina's zoals Toevoegen en Instellingen
  behouden bewust de smallere, leesbare breedte.
- De controle bij De Poort op nieuwe nummers per reeks werkte tot nu toe enkel
  per reeks apart, op een knop per rij. Dat is vervangen door één controle
  die alle reeksen doorloopt: automatisch één keer per week op de
  achtergrond, en op elk moment ook zelf te starten met de knop "Controleer
  nu bij De Poort". Tussen twee reeksen zit telkens een vaste pauze, zodat
  deze controle nooit als een stortvloed van aanvragen bij De Poort
  binnenkomt. Het laatste resultaat per reeks wordt bewaard en blijft
  zichtbaar na het herladen van de pagina.
- De reeksenpagina toont voortaan enkel de ontbrekende nummers en het
  resultaat van de laatste controle bij De Poort; "in bezit" en "hoogste
  nummer" stonden er vooral ter info en maakten de tabel breder dan nodig.
  Er staan nu ook filters op type, eigenaar, reeks en auteur, net als op de
  volledige lijst.

## 0.1.7

- Massa-import uit Excel gaf een 500-fout zodra een tekstveld — reeks, auteur,
  collectie, commentaar, muzikant of een taal — toevallig een getal bevatte.
  Excel levert zo'n cel als een getal aan in plaats van als tekst, en de
  validatiefunctie ging er onterecht van uit dat alle invoer al tekst was.
  Getallen worden nu ook in tekstvelden aanvaard; een heel getal zoals 12.0
  wordt daarbij als "12" weergegeven, niet als "12.0".

## 0.1.6

- Het invulformulier reageerde in de Vivaldi-browser en in de Companion-app op
  Android niet meer op een wisseling van type, terwijl hetzelfde in Chrome en
  Edge wel werkte. De oorzaak lag niet bij de browser, maar bij de service
  worker van de Home Assistant-frontend: die slaat elk bestand waarvan de URL
  "/static/" bevat blijvend op, ook bestanden van een add-on achter Ingress, en
  negeert daarbij het versienummer dat een nieuw opgehaald bestand had moeten
  afdwingen. Wie de app al eens via Home Assistant geopend had, bleef zo
  vastzitten aan de JavaScript en stijl van een oudere versie. Statische
  bestanden staan voortaan onder `/assets` in plaats van `/static`, een pad dat
  de service worker niet apart behandelt.

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
