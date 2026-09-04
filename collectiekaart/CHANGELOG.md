# Wijzigingen

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
