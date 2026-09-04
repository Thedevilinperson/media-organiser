# Wijzigingen

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
