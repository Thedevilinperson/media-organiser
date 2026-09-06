"""
Automatisch invullen van velden.

1. Barcode (ISBN/EAN) -> een reeks gratis catalogi zonder sleutel. Welke dat
   zijn en waarom, staat in `services/barcode_sources.py`. Kort: Google Books,
   Open Library, de Koninklijke Bibliotheek (GGC), Wikidata, de BnF, openBD en
   MusicBrainz, plus zoeklinks naar Stripinfo, LastDodo en Boekwinkeltjes voor
   wat geen open interface heeft.
2. Foto van de kaft:
   - zonder AI: lokale OCR met tesseract (geen internet nodig);
   - met AI (optioneel): een vision-model dat titel/reeks/nummer/auteur
     herkent. Kan ook een lokaal draaiend LLM zijn.
"""
import base64
import json
import re

import requests

from services import barcode_sources
from services.barcode_sources import Code, ean_checksum_ok  # noqa: F401  (blijft hier bruikbaar)

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:  # pragma: no cover
    OCR_AVAILABLE = False

TIMEOUT = 8

# Enkel deze velden worden overgenomen uit een externe bron. Alles wat een
# API of een AI-model extra terugstuurt, wordt genegeerd (zie SECURITY.md,
# bevinding B5).
ALLOWED_LOOKUP_FIELDS = {
    "title", "series", "series_number", "author",
    "year", "musician", "barcode", "collection",
}


def _filter_fields(raw):
    """Houdt enkel bekende velden over en kapt te lange waarden af."""
    clean = {}
    if not isinstance(raw, dict):
        return clean
    for key, value in raw.items():
        if key not in ALLOWED_LOOKUP_FIELDS:
            continue
        if value is None or isinstance(value, (dict, list)):
            continue
        text = str(value).strip()
        if text:
            clean[key] = text[:300]
    return clean


# ---------------------------------------------------------------------------
# 1. Barcode (geen AI nodig)
# ---------------------------------------------------------------------------
# Een kleine cache in het geheugen. Scan je per ongeluk twee keer dezelfde
# code, of ga je terug in de browser, dan worden zeven catalogi niet opnieuw
# lastiggevallen. Bewust klein en zonder vervaldatum: het proces herstart vaak
# genoeg en boekgegevens wijzigen niet.
_CACHE = {}
_CACHE_MAX = 200


def lookup_barcode_detailed(code):
    """
    Zoekt een ISBN of EAN op bij alle bronnen die er iets over kunnen weten.

    Geeft terug:
      barcode        de genormaliseerde code
      fields         de samengevoegde velden, klaar voor het formulier
      sources        de labels van de bronnen die effectief iets opleverden
      tried          de labels van alle bevraagde bronnen
      links          zoeklinks naar sites zonder open interface
      found          of er iets bruikbaars uit kwam
      kind           'isbn', 'ean' of 'onbekend'
      suggested_type een gok voor het mediatype ('boek', 'strip', 'cd')

    Elke bron faalt zacht. Ligt er één plat of is ze traag, dan blijven de
    andere gewoon gelden.
    """
    info = Code(code)
    if not info.raw:
        return {"barcode": "", "fields": {}, "sources": [], "tried": [],
                "links": [], "found": False, "kind": "onbekend", "suggested_type": None}

    if info.raw in _CACHE:
        return _CACHE[info.raw]

    resultaten = barcode_sources.gather(info)
    velden = _filter_fields(barcode_sources.merge(info, resultaten))
    velden["barcode"] = info.raw

    labels = [barcode_sources.SOURCES[naam][0] for naam in resultaten]
    tried = [barcode_sources.SOURCES[naam][0]
             for naam in barcode_sources.relevant_sources(info)]

    antwoord = {
        "barcode": info.raw,
        "fields": velden,
        "sources": labels,
        "tried": tried,
        "links": barcode_sources.search_links(info, velden.get("title")),
        "found": bool(velden.get("title")),
        "kind": "isbn" if info.is_isbn else ("ean" if len(info.raw) >= 12 else "onbekend"),
        "suggested_type": _guess_type(info, resultaten, velden),
    }

    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[info.raw] = antwoord
    return antwoord


def _guess_type(info, resultaten, velden):
    """
    Een gok voor het mediatype, zodat het formulier meteen op het juiste type
    staat. Alleen een suggestie: je kan het bovenaan het formulier wijzigen.
    """
    if "musicbrainz" in resultaten:
        return "cd"
    if not info.is_isbn or not velden.get("title"):
        return None
    if velden.get("series") or velden.get("series_number"):
        return "strip"
    return "boek"


def lookup_barcode(code):
    """
    Dezelfde opzoeking, maar met enkel de velden terug. Blijft bestaan omdat
    de import en oudere aanroepen hierop rekenen.
    """
    return lookup_barcode_detailed(code)["fields"]


# ---------------------------------------------------------------------------
# 2a. Foto zonder AI: lokale OCR
# ---------------------------------------------------------------------------
def analyze_cover_ocr(image_path):
    """
    Leest de tekst op de kaft met tesseract, volledig lokaal en zonder
    internet. Dit blijft een ruwe gok: de langste tekstregel wordt als
    titelkandidaat voorgesteld, en een patroon als 'nr 12' of 'T12' wordt
    als reeksnummer herkend. Werkt het best bij een scherpe, rechte foto.
    """
    if not OCR_AVAILABLE:
        return {
            "ok": False,
            "error": "Lokale tekstherkenning is niet beschikbaar: installeer Tesseract OCR "
                     "(zie handleiding) of stel een AI-sleutel in bij Instellingen.",
            "fields": {},
        }
    try:
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img, lang="nld+eng+fra")
    except Exception as exc:
        return {"ok": False, "error": f"Tekstherkenning mislukt: {exc}", "fields": {}}

    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 2]
    if not lines:
        return {"ok": True, "error": None, "fields": {}, "raw_text": text}

    fields = {"title": max(lines, key=len)}

    number = re.search(r"\b(?:T|nr\.?|n[°o]|deel|#)\s*(\d{1,3})\b", text, re.I)
    if number:
        fields["series_number"] = number.group(1)

    return {"ok": True, "error": None, "fields": _filter_fields(fields), "raw_text": text[:4000]}


# ---------------------------------------------------------------------------
# 2b. Foto met AI (optioneel)
# ---------------------------------------------------------------------------
def analyze_cover_ai(image_path, api_key, base_url=None, model="claude-sonnet-4-6"):
    """
    Stuurt de kaftfoto naar een vision-model dat titel, reeks, nummer en
    auteur herkent. Wordt alleen gebruikt als je zelf een sleutel invult bij
    Instellingen; zonder sleutel valt de app terug op de OCR hierboven.

    Voor een lokaal draaiend LLM met een Anthropic-compatibele API vul je bij
    Instellingen het eigen adres in als 'AI-endpoint' (bv.
    http://192.168.0.20:8080/v1/messages). Er verlaat dan geen enkele foto je
    eigen netwerk.
    """
    if not api_key:
        return {"ok": False, "error": "Geen AI-sleutel ingesteld.", "fields": {}}

    url = base_url or "https://api.anthropic.com/v1/messages"
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "Ongeldig AI-endpoint ingesteld.", "fields": {}}

    try:
        with open(image_path, "rb") as fh:
            image_b64 = base64.b64encode(fh.read()).decode("utf-8")
    except OSError as exc:
        return {"ok": False, "error": f"Kon de foto niet lezen: {exc}", "fields": {}}

    media_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

    prompt = (
        "Dit is een foto van de kaft van een strip, boek, cd of dvd. "
        "Geef ENKEL een JSON-object terug (geen uitleg, geen markdown) met de velden "
        "die je met zekerheid herkent uit: title, series, series_number, author, year, "
        "musician. Laat velden die je niet zeker weet gewoon weg."
    )

    try:
        resp = requests.post(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        raw = "\n".join(blocks).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        return {"ok": True, "error": None, "fields": _filter_fields(json.loads(raw))}
    except Exception as exc:
        return {"ok": False, "error": f"AI-analyse mislukt: {exc}", "fields": {}}
