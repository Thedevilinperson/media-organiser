"""
Bronnen voor het opzoeken van een barcode (ISBN of EAN).

Waarom er zo veel zijn
----------------------
Google Books en Open Library dekken Engelstalig werk behoorlijk, maar laten het
afweten bij Nederlandstalige uitgaven en zeker bij strips. Vlaamse en
Nederlandse uitgevers leveren hun gegevens aan het Centraal Boekhuis en aan de
Koninklijke Bibliotheek, niet aan Google. Daarom worden hier meerdere catalogi
naast elkaar bevraagd. Allemaal gratis, allemaal zonder sleutel of account.

De bronnen, en wat ze goed doen:

- Google Books ....... breed, ook veel Nederlandse handelsuitgaven
- Open Library ....... Engelstalig sterk, drie ingangen (books, isbn, search)
- KB / GGC ........... de Nederlandse nationale bibliografie via SRU; de beste
                       bron voor Nederlandstalige boeken én stripalbums
- Wikidata ........... geeft als enige vaak reeks + nummer bij stripalbums
- BnF ................ Franse nationale bibliotheek, voor Franstalige BD en
                       voor albums waarvan de vertaling het ISBN deelt
- DNB ................ Deutsche Nationalbibliothek, voor Duitstalige uitgaven
                       en voor albums die enkel daar beschreven staan
- openBD ............. Japanse uitgaven, voor manga in het origineel
- MusicBrainz ........ EAN-codes van cd's en dvd's; die staan in géén enkele
                       boekencatalogus, en zijn de meest voorkomende reden dat
                       een scan vroeger niets opleverde
- UPCitemdb .......... algemene EAN-databank; vangt dvd-boxen, verzamelaars-
                       uitgaven en cd's op die MusicBrainz niet kent

Voor bronnen zonder open interface (Stripinfo, LastDodo, Boekwinkeltjes) wordt
er niets geschraapt. Die geven een zoeklink terug, net zoals bij de richtprijs.
Dat is dezelfde bewuste keuze als in `value_estimation.py`.

Alle bronnen falen zacht: valt er één weg, dan blijven de andere gewoon werken.
Ze worden parallel bevraagd met een gezamenlijke tijdslimiet, zodat het geheel
niet trager is dan de traagste bron die op tijd antwoordt.

Rapportering per bron
---------------------
Sinds 0.1.14 houdt elke bron bij wat er precies gebeurde: welke adressen
bevraagd werden, welke HTTP-code er terugkwam, hoe lang het duurde en of er
iets bruikbaars uit kwam. Dat verschil is belangrijk: "de bron antwoordde netjes
dat ze deze code niet kent" is iets heel anders dan "de bron gaf een 403 en werd
dus nooit echt bevraagd". Vroeger zagen die twee er op het scherm identiek uit,
waardoor een storing als "niets gevonden" gelezen werd. Zie `SourceReport`.
"""
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import quote, urlencode

import requests

from version import __version__

# Per bron kort; het geheel wordt begrensd door TOTAL_BUDGET hieronder.
TIMEOUT = 7
SPARQL_TIMEOUT = 12
TOTAL_BUDGET = 16  # seconden die het volledige opzoeken hoogstens mag duren

# Wikidata en MusicBrainz vragen uitdrukkelijk om een herkenbare User-Agent
# met een contactmogelijkheid. Zonder die kop knippen ze de verbinding door.
USER_AGENT = (
    f"Collectiekaart/{__version__} (persoonlijke collectiebeheerder; "
    "https://github.com/Thedevilinperson/media-organiser)"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.6"}


# ---------------------------------------------------------------------------
# Rapport per bron
# ---------------------------------------------------------------------------
STATUS_LABELS = {
    "found": "gevonden",
    "empty": "niets gevonden",
    "error": "fout",
    "timeout": "te traag",
    "skipped": "overgeslagen",
}


class SourceReport:
    """
    Wat één bron gedaan heeft. Wordt onveranderd doorgegeven aan de scanpagina,
    zodat je daar kan zien of een lege uitkomst een storing was of gewoon een
    code die de bron niet kent.
    """

    def __init__(self, key, label):
        self.key = key
        self.label = label
        self.status = "empty"
        self.message = ""
        self.calls = []
        self.fields = {}
        self.ms = 0
        self.blocked = False

    def geblokkeerd(self):
        """
        Of het nog zin heeft deze bron verder te bevragen.

        Weigert een bron twee keer na elkaar (401, 403 of 429), dan gaat ze dat
        de derde keer ook doen. Vroeger werden alle ISBN-vormen en alle
        landcodes toch afgewerkt; bij Google Books alleen al waren dat zeven
        aanvragen die elk in hun eigen time-out liepen, wat het opzoeken
        onnodig traag maakte terwijl het antwoord al vaststond.
        """
        geweigerd = [c for c in self.calls if c["http"] in (401, 403, 429)]
        return len(geweigerd) >= 2

    def add_call(self, url, http_status=None, error=None, ms=0, note=None):
        self.calls.append({
            "url": str(url)[:220],
            "http": http_status,
            "error": error,
            "ms": int(ms),
            "note": note,
        })

    def note_last(self, note):
        if self.calls:
            self.calls[-1]["note"] = note

    def skip(self, reason):
        self.status = "skipped"
        self.message = reason

    def _summarise(self):
        """Bouwt een leesbare samenvatting op uit de losse aanvragen."""
        if self.status in ("skipped", "timeout"):
            return
        if self.fields:
            self.status = "found"
            self.message = "leverde: " + ", ".join(sorted(self.fields))
            return

        gelukt = [c for c in self.calls if c["error"] is None and c["http"] and c["http"] < 400]
        mislukt = [c for c in self.calls if c["error"] is not None or (c["http"] or 0) >= 400]
        if not self.calls:
            self.status = "error"
            self.message = "geen enkele aanvraag verstuurd"
        elif gelukt:
            self.status = "empty"
            self.message = "antwoordde, maar kent deze code niet"
            if mislukt:
                self.message += f" ({len(mislukt)} van de {len(self.calls)} aanvragen mislukte)"
        else:
            self.status = "error"
            echt = [c for c in mislukt if c["http"] is not None] or mislukt
            eerste = echt[0]
            self.message = eerste["error"] or _explain_http(eerste["http"])
            if self.blocked:
                self.message += " — de overige aanvragen zijn overgeslagen"

    def as_dict(self):
        self._summarise()
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "status_label": STATUS_LABELS.get(self.status, self.status),
            "message": self.message,
            "ms": int(self.ms),
            "fields": sorted(self.fields),
            "calls": self.calls,
        }


def _explain_http(code):
    """Vertaalt een HTTP-code naar iets waar je zonder handboek iets aan hebt."""
    if code is None:
        return "geen antwoord"
    if code == 400:
        return "HTTP 400 — de bron begreep de zoekopdracht niet"
    if code in (401, 403):
        return f"HTTP {code} — de bron weigert deze aanvraag (geen storing, een keuze van hen)"
    if code == 404:
        return "HTTP 404 — dat adres bestaat niet (meer) bij deze bron"
    if code == 429:
        return "HTTP 429 — te veel aanvragen na elkaar; even wachten helpt"
    if 500 <= code < 600:
        return f"HTTP {code} — storing bij de bron zelf"
    return f"HTTP {code}"


# ---------------------------------------------------------------------------
# ISBN's normaliseren
# ---------------------------------------------------------------------------
class Code:
    """
    Eén gescande code in al haar vormen.

    Veel catalogi kennen een uitgave alleen onder haar ISBN-10, andere alleen
    onder het ISBN-13. Door beide vormen te berekenen en allebei mee te sturen
    wordt een uitgave gevonden die anders "onbekend" zou blijven. Dat alleen al
    scheelt merkbaar bij oudere Nederlandse boeken en stripalbums.
    """

    def __init__(self, raw):
        self.raw = re.sub(r"[^0-9Xx]", "", str(raw or "")).upper()[:20]
        self.isbn13 = None
        self.isbn10 = None

        if len(self.raw) == 13 and self.raw.isdigit() and self.raw[:3] in ("978", "979"):
            self.isbn13 = self.raw
            self.isbn10 = _isbn13_to_10(self.raw)
        elif len(self.raw) == 10:
            self.isbn10 = self.raw
            self.isbn13 = _isbn10_to_13(self.raw)

    @property
    def is_isbn(self):
        return bool(self.isbn13)

    @property
    def variants(self):
        """De ISBN-vormen die het proberen waard zijn, zonder dubbels."""
        return [v for v in (self.isbn13, self.isbn10) if v]

    @property
    def group(self):
        """
        De taalgroep uit het ISBN: '90'/'94' is Nederlandstalig, '2' Frans,
        '4' Japans, '0'/'1' Engels, '3' Duits. Bepaalt welke bron als eerste
        geloofd wordt bij tegenstrijdige gegevens.
        """
        if not self.isbn13:
            return ""
        rest = self.isbn13[3:]
        for prefix in ("90", "94", "84", "88"):
            if rest.startswith(prefix):
                return prefix
        return rest[0]

    @property
    def region(self):
        group = self.group
        if group in ("90", "94"):
            return "nl"
        if group == "2":
            return "fr"
        if group == "4":
            return "jp"
        if group == "3":
            return "de"
        if group in ("0", "1"):
            return "en"
        return "onbekend"


def _isbn13_to_10(isbn13):
    if not isbn13.startswith("978"):
        return None  # 979-nummers hebben geen ISBN-10-tegenhanger
    body = isbn13[3:12]
    total = sum((10 - i) * int(digit) for i, digit in enumerate(body))
    check = (11 - total % 11) % 11
    return body + ("X" if check == 10 else str(check))


def _isbn10_to_13(isbn10):
    body = "978" + isbn10[:9]
    if not body.isdigit():
        return None
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


def ean_checksum_ok(code):
    """
    Controleert het controlecijfer van een EAN-13 of UPC-A.

    EAN-8 wordt bewust geweigerd: dat formaat komt niet voor op boeken of
    strips, en een half gelezen EAN-13 ziet er soms uit als een geldige EAN-8.
    """
    code = str(code or "")
    if not code.isdigit():
        return False
    if len(code) == 12:
        # Een UPC-A begint nooit met 97; zo'n code is een ISBN waarvan er een
        # cijfer wegviel bij het scannen.
        if code.startswith("97"):
            return False
        code = "0" + code
    if len(code) != 13:
        return False
    digits = [int(c) for c in code]
    check = digits.pop()
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10 == check


# ---------------------------------------------------------------------------
# Kleine hulpjes
# ---------------------------------------------------------------------------
def _year(text):
    match = re.search(r"(1[5-9]\d{2}|20\d{2})", str(text or ""))
    return match.group(1) if match else None


def _clean(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.strip(" .,:;/-") or None


def _first_text(node, *names):
    """Zoekt in een XML-fragment de eerste tag met een van deze lokale namen."""
    for element in node.iter():
        if element.tag.split("}")[-1].lower() in names and (element.text or "").strip():
            return element.text.strip()
    return None


def _all_text(node, *names):
    found = []
    for element in node.iter():
        if element.tag.split("}")[-1].lower() in names and (element.text or "").strip():
            found.append(element.text.strip())
    return found


# ---------------------------------------------------------------------------
# 1. Google Books
# ---------------------------------------------------------------------------
def google_books(code, report):
    """
    De Google Books API.

    Belangrijk detail: zonder de parameter `country` antwoordt Google op een
    aanvraag vanaf een server (een Raspberry Pi thuis, een container in Home
    Assistant) geregeld met status 403 en de melding dat het land niet bepaald
    kan worden. De aanvraag lijkt dan gewoon "niets gevonden" op te leveren,
    terwijl het boek er wel degelijk in staat. Dat verklaart een groot deel van
    de lege resultaten in oudere versies. We geven het land daarom expliciet
    mee, met België eerst.
    """
    for isbn in code.variants:
        for country in ("BE", "NL", None):
            params = {"q": f"isbn:{isbn}", "maxResults": 3}
            if country:
                params["country"] = country
            data = _get_json("https://www.googleapis.com/books/v1/volumes", params, report=report)
            items = (data or {}).get("items") or []
            report.note_last(f"{len(items)} treffer(s)" if data is not None else None)
            if items:
                return _google_item(items[0])

    # Laatste poging: de code als gewone zoekterm. Sommige uitgaven staan in
    # Google Books zonder dat het ISBN als zoeksleutel geregistreerd is.
    data = _get_json(
        "https://www.googleapis.com/books/v1/volumes",
        {"q": code.raw, "maxResults": 1, "country": "BE"},
        report=report,
    )
    items = (data or {}).get("items") or []
    report.note_last(f"{len(items)} treffer(s) op de code als zoekterm" if data is not None else None)
    return _google_item(items[0]) if items else {}


def _google_item(item):
    info = item.get("volumeInfo", {}) or {}
    title = _clean(info.get("title"))
    if not title:
        return {}
    if info.get("subtitle"):
        title = f"{title}: {_clean(info['subtitle'])}"

    found = {"title": title}
    if info.get("authors"):
        found["author"] = ", ".join(a for a in info["authors"] if a)
    year = _year(info.get("publishedDate"))
    if year:
        found["year"] = year
    return found


# ---------------------------------------------------------------------------
# 2. Open Library (drie ingangen)
# ---------------------------------------------------------------------------
def open_library(code, report):
    for isbn in code.variants or [code.raw]:
        found = (_open_library_books(isbn, report)
                 or _open_library_isbn(isbn, report)
                 or _open_library_search(isbn, report))
        if found:
            return found
    return {}


def _open_library_books(isbn, report):
    data = _get_json(
        "https://openlibrary.org/api/books",
        {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
        report=report,
    )
    book = (data or {}).get(f"ISBN:{isbn}")
    if not book:
        report.note_last("geen record voor dit ISBN" if data is not None else None)
        return {}

    found = {}
    title = _clean(book.get("title"))
    if title:
        if book.get("subtitle"):
            title = f"{title}: {_clean(book['subtitle'])}"
        found["title"] = title
    authors = [a.get("name") for a in (book.get("authors") or []) if a.get("name")]
    if authors:
        found["author"] = ", ".join(authors)
    year = _year(book.get("publish_date"))
    if year:
        found["year"] = year
    return found


def _open_library_isbn(isbn, report):
    """De /isbn/-ingang; die kent soms een reeks die de andere niet geeft."""
    data = _get_json(f"https://openlibrary.org/isbn/{quote(isbn)}.json", None, report=report)
    if not isinstance(data, dict) or not data.get("title"):
        return {}

    found = {"title": _clean(data.get("title"))}
    year = _year(data.get("publish_date"))
    if year:
        found["year"] = year

    series = data.get("series")
    if isinstance(series, list) and series:
        reeks, nummer, _ = _split_series_entry(str(series[0]))
        found["series"] = reeks or _clean(str(series[0]))
        if nummer:
            found["series_number"] = nummer
    return {k: v for k, v in found.items() if v}


def _open_library_search(isbn, report):
    data = _get_json("https://openlibrary.org/search.json", {"isbn": isbn, "limit": 1}, report=report)
    docs = (data or {}).get("docs") or []
    report.note_last(f"{len(docs)} treffer(s)" if data is not None else None)
    if not docs:
        return {}
    doc = docs[0]

    found = {}
    if doc.get("title"):
        found["title"] = _clean(doc["title"])
    if doc.get("author_name"):
        found["author"] = ", ".join(doc["author_name"][:3])
    if doc.get("first_publish_year"):
        found["year"] = str(doc["first_publish_year"])
    return found


# ---------------------------------------------------------------------------
# 3. Koninklijke Bibliotheek (NL) — GGC via SRU
# ---------------------------------------------------------------------------
# De GGC aanvaardt niet één maar meerdere schrijfwijzen voor een ISBN-zoekvraag,
# en welke ervan werkt hangt af van de versie van hun SRU-laag. Vroeger werd er
# maar één vorm geprobeerd; klopte die niet, dan kwam er een lege lijst terug
# die niet van "onbekend ISBN" te onderscheiden was. Nu worden ze na elkaar
# geprobeerd tot er een record uitkomt, en staat in het rapport welke vorm het
# deed.
KB_QUERIES = ["isbn={isbn}", 'isbn any "{isbn}"', "dc.identifier={isbn}"]


def kb_ggc(code, report):
    """
    De Gemeenschappelijke Geautomatiseerde Catalogus van de Koninklijke
    Bibliotheek in Den Haag, via hun open SRU-interface. Dit is de Nederlandse
    nationale bibliografie: zowat elke uitgave die in Nederland of Vlaanderen
    met een ISBN verscheen, staat erin — ook stripalbums, wat bij Google
    Books lang niet altijd het geval is.
    """
    for isbn in code.variants:
        for vorm in KB_QUERIES:
            root = _get_xml(
                "https://jsru.kb.nl/sru/sru",
                {
                    "operation": "searchRetrieve",
                    "version": "1.2",
                    "x-collection": "GGC",
                    "recordSchema": "dc",
                    "maximumRecords": "1",
                    "query": vorm.format(isbn=isbn),
                },
                report=report,
            )
            if root is None:
                continue
            found = _dublin_core(root)
            report.note_last("record gevonden" if found else "0 records")
            if found:
                return found
    return {}


# ---------------------------------------------------------------------------
# 4. Bibliothèque nationale de France — SRU
# ---------------------------------------------------------------------------
def bnf(code, report):
    """
    Voor Franstalige albums. Veel Vlaamse en Nederlandse strips zijn
    vertalingen; staat de Nederlandse uitgave nergens, dan levert de Franse
    ingang vaak toch de reeks en de auteur op.
    """
    for isbn in code.variants:
        root = _get_xml(
            "https://catalogue.bnf.fr/api/SRU",
            {
                "version": "1.2",
                "operation": "searchRetrieve",
                "recordSchema": "dublincore",
                "maximumRecords": "1",
                "query": f'bib.isbn all "{isbn}"',
            },
            report=report,
        )
        if root is None:
            continue
        found = _dublin_core(root)
        report.note_last("record gevonden" if found else "0 records")
        if found:
            return found
    return {}


# ---------------------------------------------------------------------------
# 5. Deutsche Nationalbibliothek — SRU
# ---------------------------------------------------------------------------
def dnb(code, report):
    """
    De Duitse nationale bibliografie. Nieuw in 0.1.14. Voegt weinig toe voor
    een Nederlands album, maar vangt Duitstalige manga-uitgaven en comics op —
    en het kost niets, want alle bronnen worden toch naast elkaar bevraagd.
    """
    for isbn in code.variants:
        root = _get_xml(
            "https://services.dnb.de/sru/dnb",
            {
                "version": "1.1",
                "operation": "searchRetrieve",
                "query": f"NUM={isbn}",
                "recordSchema": "oai_dc",
                "maximumRecords": "1",
            },
            report=report,
        )
        if root is None:
            continue
        found = _dublin_core(root)
        report.note_last("record gevonden" if found else "0 records")
        if found:
            return found
    return {}


def _dublin_core(root):
    """
    Haalt titel, auteur en jaar uit een SRU-antwoord in Dublin Core. Werkt op
    de lokale tagnaam, zodat het niet uitmaakt welke naamruimte een catalogus
    gebruikt — die verschilt per bibliotheek en wijzigt al eens.
    """
    title = _first_text(root, "title")
    if not title:
        return {}

    found = {"title": _clean(title)}
    reeks, nummer, resttitel = _split_series_entry(title)
    if reeks:
        found["series"] = reeks
        found["title"] = resttitel or _clean(title)
    if nummer:
        found["series_number"] = nummer

    makers = _all_text(root, "creator", "contributor")
    if makers:
        # Bibliotheken noteren "Vandersteen, Willy, 1913-1990"; de jaartallen
        # horen niet in het auteursveld thuis.
        schoon = [re.sub(r",?\s*\d{4}\s*-\s*\d{0,4}\.?$", "", m).strip(" .,") for m in makers[:3]]
        found["author"] = ", ".join(dict.fromkeys(s for s in schoon if s))

    year = _year(" ".join(_all_text(root, "date")))
    if year:
        found["year"] = year
    return {k: v for k, v in found.items() if v}


# ---------------------------------------------------------------------------
# 6. Wikidata — de enige bron die vaak reeks én nummer kent
# ---------------------------------------------------------------------------
def wikidata(code, report):
    """
    Stripalbums staan verrassend goed op Wikidata, mét "onderdeel van de reeks"
    en het nummer daarin. Dat zijn net de twee velden die de boekencatalogi
    zelden invullen en die je bij een strip het meest nodig hebt.

    De ISBN's staan er met streepjes in, en die streepjes staan niet vast.
    Daarom wordt er op de genormaliseerde vorm vergeleken.
    """
    if not code.isbn13:
        report.skip("geen ISBN: Wikidata kent deze code niet als boek")
        return {}

    isbn13 = code.isbn13
    isbn10 = code.isbn10 or ""
    query = f"""
SELECT ?itemLabel ?authorLabel ?date ?seriesLabel ?ordinal WHERE {{
  {{ ?item wdt:P212 ?raw13 . FILTER(REPLACE(?raw13, "[^0-9Xx]", "") = "{isbn13}") }}
  UNION
  {{ ?item wdt:P957 ?raw10 . FILTER(REPLACE(?raw10, "[^0-9Xx]", "") = "{isbn10}") }}
  OPTIONAL {{ ?item wdt:P50 ?author. }}
  OPTIONAL {{ ?item wdt:P577 ?date. }}
  OPTIONAL {{ ?item p:P179 ?statement. ?statement ps:P179 ?series.
             OPTIONAL {{ ?statement pq:P1545 ?ordinal. }} }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "nl,en,fr,de". }}
}} LIMIT 3
"""
    data = _get_json(
        "https://query.wikidata.org/sparql",
        {"query": query, "format": "json"},
        timeout=SPARQL_TIMEOUT,
        report=report,
    )
    rows = ((data or {}).get("results") or {}).get("bindings") or []
    report.note_last(f"{len(rows)} treffer(s)" if data is not None else None)
    if not rows:
        return {}

    row = rows[0]

    def value(key):
        return (row.get(key) or {}).get("value")

    found = {}
    if value("itemLabel") and not re.match(r"^Q\d+$", value("itemLabel")):
        found["title"] = _clean(value("itemLabel"))
    if value("authorLabel"):
        found["author"] = _clean(value("authorLabel"))
    if value("seriesLabel"):
        found["series"] = _clean(value("seriesLabel"))
    if value("ordinal"):
        found["series_number"] = _clean(value("ordinal"))
    year = _year(value("date"))
    if year:
        found["year"] = year
    return found


# ---------------------------------------------------------------------------
# 7. openBD — Japanse uitgaven (manga in het origineel)
# ---------------------------------------------------------------------------
def openbd(code, report):
    if not code.isbn13 or code.region != "jp":
        report.skip("enkel voor Japanse ISBN's (978-4…)")
        return {}
    data = _get_json("https://api.openbd.jp/v1/get", {"isbn": code.isbn13}, report=report)
    if not isinstance(data, list) or not data or not data[0]:
        report.note_last("geen record" if data is not None else None)
        return {}

    summary = (data[0] or {}).get("summary") or {}
    found = {}
    if summary.get("title"):
        found["title"] = _clean(summary["title"])
    if summary.get("author"):
        found["author"] = _clean(summary["author"])
    if summary.get("series"):
        found["series"] = _clean(summary["series"])
    year = _year(summary.get("pubdate"))
    if year:
        found["year"] = year
    return found


# ---------------------------------------------------------------------------
# 8. MusicBrainz — cd's en dvd's
# ---------------------------------------------------------------------------
def musicbrainz(code, report):
    """
    Een cd of dvd draagt een gewone EAN, geen ISBN. Die code staat in geen
    enkele boekencatalogus, en dat is veruit de vaakst voorkomende reden dat
    een scan vroeger niets opleverde. MusicBrainz kent wél barcodes.
    """
    if code.is_isbn or len(code.raw) < 12:
        report.skip("enkel voor EAN-codes van cd's en dvd's")
        return {}

    data = _get_json(
        "https://musicbrainz.org/ws/2/release",
        {"query": f"barcode:{code.raw}", "fmt": "json", "limit": "1"},
        report=report,
    )
    releases = (data or {}).get("releases") or []
    report.note_last(f"{len(releases)} treffer(s)" if data is not None else None)
    if not releases:
        return {}

    release = releases[0]
    found = {}
    if release.get("title"):
        found["title"] = _clean(release["title"])
    artists = [c.get("name") for c in (release.get("artist-credit") or []) if c.get("name")]
    if artists:
        found["musician"] = ", ".join(artists[:3])
        found["author"] = found["musician"]
    year = _year(release.get("date"))
    if year:
        found["year"] = year
    return found


# ---------------------------------------------------------------------------
# 9. UPCitemdb — algemene EAN-databank
# ---------------------------------------------------------------------------
def upcitemdb(code, report):
    """
    Een vrij te gebruiken proefingang op een algemene barcodedatabank. Nieuw in
    0.1.14, en bedoeld voor precies dat ene geval waar alle andere bronnen op
    stuklopen: een dvd-box, een verzamelaarsuitgave of een cd die MusicBrainz
    niet kent. De gegevens zijn ruwer dan die van een bibliotheek — vaak enkel
    een titel zoals ze in de winkel heet — maar dat is nog altijd beter dan een
    leeg formulier.

    De proefingang is uitdrukkelijk begrensd in aantal aanvragen per dag. Loop
    je daartegen aan, dan komt er een 429 terug en zie je dat gewoon staan bij
    de bronnen.
    """
    if code.is_isbn or len(code.raw) < 12:
        report.skip("enkel voor EAN-codes van cd's, dvd's en dozen")
        return {}

    data = _get_json(
        "https://api.upcitemdb.com/prod/trial/lookup",
        {"upc": code.raw},
        report=report,
    )
    items = (data or {}).get("items") or []
    report.note_last(f"{len(items)} treffer(s)" if data is not None else None)
    if not items:
        return {}

    item = items[0]
    found = {}
    titel = _clean(item.get("title"))
    if titel:
        found["title"] = titel
    maker = _clean(item.get("artist")) or _clean(item.get("brand"))
    if maker:
        found["author"] = maker
        found["musician"] = maker
    year = _year(item.get("publish_date") or item.get("title"))
    if year:
        found["year"] = year
    return found


# ---------------------------------------------------------------------------
# Reeks en nummer uit een titel halen
# ---------------------------------------------------------------------------
SERIES_PATTERNS = [
    # "De Kiekeboes 12: Het witte bloed" / "Suske en Wiske 301 - De ..."
    re.compile(r"^(?P<reeks>.+?)\s*[,]?\s*(?:nr\.?|n[°o]|deel|vol\.?|tome|t\.)?\s*"
               r"(?P<nummer>\d{1,3}(?:[.,]5)?)\s*[:\-–—]\s*(?P<titel>.+)$", re.I),
    # "Het witte bloed (De Kiekeboes, 12)"
    re.compile(r"^(?P<titel>.+?)\s*\(\s*(?P<reeks>.+?)[,;]?\s*(?:nr\.?|n[°o]|#|deel)?\s*"
               r"(?P<nummer>\d{1,3}(?:[.,]5)?)\s*\)$", re.I),
]


def _split_series_entry(text):
    """
    Probeert uit één regel een reeksnaam, een nummer en de eigenlijke titel te
    halen. Bewust voorzichtig: er wordt alleen gesplitst bij een duidelijk
    patroon, want een verkeerde gok kost meer tijd dan een leeg veld.

    Geeft (reeks, nummer, titel) terug; elk deel mag None zijn.
    """
    text = _clean(text) or ""
    if not text:
        return None, None, None
    for pattern in SERIES_PATTERNS:
        match = pattern.match(text)
        if match:
            reeks = _clean(match.group("reeks"))
            nummer = (match.group("nummer") or "").replace(",", ".") or None
            titel = _clean(match.group("titel"))
            if reeks and len(reeks) > 2 and not reeks.isdigit():
                return reeks, nummer, titel
    return None, None, None


def series_from_title(title):
    """Publieke variant, ook gebruikt door de verrijking met je eigen collectie."""
    return _split_series_entry(title)


# ---------------------------------------------------------------------------
# Zoeklinks voor bronnen zonder open interface
# ---------------------------------------------------------------------------
def search_links(code, title=None):
    """
    Stripinfo, LastDodo en Boekwinkeltjes hebben geen open interface en laten
    geautomatiseerde aanvragen niet toe. Daar wordt dus niets geschraapt; je
    krijgt een zoeklink, net zoals bij de richtprijs.
    """
    term = title or code.raw
    links = [
        {"label": "Stripinfo.be",
         "url": "https://www.stripinfo.be/zoek/zoek?" + urlencode({"zoekstring": term})},
        {"label": "LastDodo",
         "url": "https://www.lastdodo.nl/nl/search?" + urlencode({"q": term})},
        {"label": "Boekwinkeltjes",
         "url": "https://www.boekwinkeltjes.nl/zoeken/?" + urlencode({"q": term})},
        {"label": "Google",
         "url": "https://www.google.com/search?" + urlencode({"q": term})},
    ]
    return links


# ---------------------------------------------------------------------------
# Netwerk
# ---------------------------------------------------------------------------
def _request(url, params, timeout, accept, report):
    """
    Eén HTTP-aanvraag, met alles wat er misging netjes genoteerd in het
    rapport. Geeft het antwoord terug, of None als er niets bruikbaars kwam.
    """
    if report is not None and report.geblokkeerd():
        if not report.blocked:
            report.blocked = True
            report.add_call(url, None, "verdere aanvragen overgeslagen: deze bron weigerde er al twee", 0)
        return None

    started = time.monotonic()
    volledig = url + (("?" + urlencode(params, doseq=True)) if params else "")
    try:
        resp = requests.get(url, params=params, timeout=timeout,
                            headers={**HEADERS, "Accept": accept})
    except requests.exceptions.Timeout:
        report and report.add_call(volledig, None, f"geen antwoord binnen {timeout} s",
                                   _ms(started))
        return None
    except requests.exceptions.SSLError:
        report and report.add_call(volledig, None, "beveiligde verbinding mislukt", _ms(started))
        return None
    except requests.exceptions.ConnectionError:
        report and report.add_call(volledig, None,
                                   "geen verbinding (bron onbereikbaar of geen internet)",
                                   _ms(started))
        return None
    except Exception as exc:  # pragma: no cover — vangnet, mag nooit doorslaan
        report and report.add_call(volledig, None, f"onverwachte fout: {type(exc).__name__}",
                                   _ms(started))
        return None

    duur = _ms(started)
    adres = getattr(resp, "url", volledig) or volledig
    if resp.status_code >= 400:
        report and report.add_call(adres, resp.status_code, None, duur)
        return None
    report and report.add_call(adres, resp.status_code, None, duur)
    return resp


def _ms(started):
    return round((time.monotonic() - started) * 1000)


def _get_json(url, params, timeout=TIMEOUT, report=None):
    resp = _request(url, params, timeout, "application/json", report)
    if resp is None:
        return None
    try:
        return resp.json()
    except ValueError:
        report and report.note_last("antwoord was geen geldige JSON")
        return None


def _get_xml(url, params, timeout=TIMEOUT, report=None):
    resp = _request(url, params, timeout, "application/xml", report)
    if resp is None:
        return None
    try:
        return ET.fromstring(resp.content)
    except ET.ParseError:
        report and report.note_last("antwoord was geen geldige XML")
        return None


# ---------------------------------------------------------------------------
# Alle bronnen samen
# ---------------------------------------------------------------------------
# naam -> (label voor op het scherm, functie)
SOURCES = {
    "google": ("Google Books", google_books),
    "openlibrary": ("Open Library", open_library),
    "kb": ("Koninklijke Bibliotheek (GGC)", kb_ggc),
    "wikidata": ("Wikidata", wikidata),
    "bnf": ("Bibliothèque nationale de France", bnf),
    "dnb": ("Deutsche Nationalbibliothek", dnb),
    "openbd": ("openBD (Japan)", openbd),
    "musicbrainz": ("MusicBrainz", musicbrainz),
    "upcitemdb": ("UPCitemdb", upcitemdb),
}

# Welke bron als eerste geloofd wordt bij tegenstrijdige gegevens, per
# taalgebied van het ISBN. Een Nederlands boek beschrijft de KB nu eenmaal
# beter dan Google, een Frans album de BnF.
PRIORITY = {
    "nl": ["kb", "google", "openlibrary", "wikidata", "bnf", "dnb", "openbd", "musicbrainz", "upcitemdb"],
    "fr": ["bnf", "google", "kb", "openlibrary", "wikidata", "dnb", "openbd", "musicbrainz", "upcitemdb"],
    "jp": ["openbd", "google", "openlibrary", "wikidata", "kb", "bnf", "dnb", "musicbrainz", "upcitemdb"],
    "de": ["dnb", "google", "openlibrary", "kb", "wikidata", "bnf", "openbd", "musicbrainz", "upcitemdb"],
    "en": ["openlibrary", "google", "wikidata", "kb", "bnf", "dnb", "openbd", "musicbrainz", "upcitemdb"],
    "onbekend": ["musicbrainz", "upcitemdb", "google", "openlibrary", "kb", "wikidata", "bnf", "dnb", "openbd"],
}

# Reeks en nummer verdienen een eigen volgorde: Wikidata vult die als enige
# betrouwbaar in, ook al is haar titel soms minder bruikbaar.
FIELD_PRIORITY = {
    "series": ["wikidata", "openbd", "kb", "openlibrary", "bnf", "dnb", "google"],
    "series_number": ["wikidata", "openbd", "kb", "openlibrary", "bnf", "dnb", "google"],
    "musician": ["musicbrainz", "upcitemdb"],
}


def _volgorde(region):
    """De prioriteitslijst, aangevuld met bronnen die er niet in vermeld staan."""
    basis = PRIORITY.get(region, PRIORITY["onbekend"])
    return basis + [naam for naam in SOURCES if naam not in basis]


def _relevant_sources(code):
    """Enkel bronnen bevragen die voor deze code iets kunnen opleveren."""
    if not code.raw:
        return []
    if code.is_isbn:
        namen = ["google", "openlibrary", "kb", "wikidata", "bnf", "dnb"]
        if code.region == "jp":
            namen.append("openbd")
        return namen
    return ["musicbrainz", "upcitemdb", "google"]


def relevant_sources(code):
    """Publieke variant, zodat de scanpagina kan tonen wat er bevraagd werd."""
    return _relevant_sources(code)


def gather(code):
    """
    Bevraagt alle zinvolle bronnen parallel.

    Geeft twee dingen terug:
      resultaten  {bronnaam: velden} voor de bronnen die iets opleverden
      rapporten   één SourceReport per bron, ook voor wie niets vond of stuk
                  ging — dat is precies wat de scanpagina toont

    Parallel, omdat negen bronnen na elkaar bevragen op een Raspberry Pi al
    snel een minuut duurt; samen blijft het onder de tijdslimiet hierboven.
    """
    namen = _relevant_sources(code)
    rapporten = []
    if not namen:
        return {}, rapporten

    reports = {naam: SourceReport(naam, SOURCES[naam][0]) for naam in namen}
    resultaten = {}

    def run(naam):
        gestart = time.monotonic()
        report = reports[naam]
        try:
            velden = SOURCES[naam][1](code, report) or {}
        except Exception as exc:  # een stukke bron mag de rest niet meeslepen
            report.status = "error"
            report.message = f"onverwachte fout in de bron: {type(exc).__name__}"
            velden = {}
        report.ms = _ms(gestart)
        report.fields = velden
        return velden

    pool = ThreadPoolExecutor(max_workers=len(namen))
    try:
        futures = {pool.submit(run, naam): naam for naam in namen}
        klaar, nog_bezig = wait(list(futures), timeout=TOTAL_BUDGET)
        for future in klaar:
            naam = futures[future]
            try:
                velden = future.result() or {}
            except Exception:
                velden = {}
            if velden:
                resultaten[naam] = velden
        for future in nog_bezig:
            naam = futures[future]
            reports[naam].status = "timeout"
            reports[naam].message = (
                f"nog geen antwoord na {TOTAL_BUDGET} s; de andere bronnen tellen wel mee"
            )
    finally:
        # Niet wachten op een bron die over haar tijd gaat; requests kapt zelf
        # af op haar eigen time-out en de thread verdwijnt daarna vanzelf.
        pool.shutdown(wait=False)

    rapporten = [reports[naam] for naam in namen]
    return resultaten, rapporten


def merge(code, resultaten):
    """
    Voegt de bronnen samen tot één set velden. Per veld wint de bron die voor
    dit taalgebied het meest betrouwbaar is; velden die een bron niet kent,
    worden aangevuld door de volgende.
    """
    volgorde = _volgorde(code.region)
    velden = {}
    herkomst = {}
    for veld in ("title", "series", "series_number", "author", "musician", "year"):
        for naam in FIELD_PRIORITY.get(veld, volgorde):
            waarde = (resultaten.get(naam) or {}).get(veld)
            if waarde:
                velden[veld] = waarde
                herkomst[veld] = naam
                break
        if veld not in velden:
            for naam in volgorde:
                waarde = (resultaten.get(naam) or {}).get(veld)
                if waarde:
                    velden[veld] = waarde
                    herkomst[veld] = naam
                    break

    # Staat de reeks nog in de titel ("De Kiekeboes 12 - Het witte bloed"),
    # haal ze er dan alsnog uit.
    if velden.get("title") and not velden.get("series"):
        reeks, nummer, resttitel = _split_series_entry(velden["title"])
        if reeks:
            velden["series"] = reeks
            herkomst["series"] = herkomst.get("title", "")
            if resttitel:
                velden["title"] = resttitel
            if nummer and not velden.get("series_number"):
                velden["series_number"] = nummer
                herkomst["series_number"] = herkomst.get("title", "")
    return velden, herkomst
