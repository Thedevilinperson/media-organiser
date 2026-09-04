"""
Automatisch invullen van velden.

1. Barcode (ISBN/EAN) -> Open Library en Google Books. Beide gratis, zonder
   sleutel en zonder AI.
2. Foto van de kaft:
   - zonder AI: lokale OCR met tesseract (geen internet nodig);
   - met AI (optioneel): een vision-model dat titel/reeks/nummer/auteur
     herkent. Kan ook een lokaal draaiend LLM zijn.
"""
import base64
import json
import re

import requests

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
def lookup_barcode(code):
    """
    Zoekt een ISBN/EAN op via gratis bronnen zonder sleutel. Werkt goed voor
    boeken; voor strips en manga is de dekking wisselend omdat niet elke
    uitgever een ISBN op de kaft zet. Ontbrekende velden vul je nadien
    manueel aan.
    """
    code = re.sub(r"[^0-9Xx]", "", code or "")[:20]
    if not code:
        return {}

    result = {}

    try:
        resp = requests.get(
            "https://openlibrary.org/api/books",
            params={"bibkeys": f"ISBN:{code}", "format": "json", "jscmd": "data"},
            timeout=TIMEOUT,
        )
        book = (resp.json() or {}).get(f"ISBN:{code}")
        if book:
            result["title"] = book.get("title", "")
            authors = book.get("authors") or []
            if authors:
                result["author"] = ", ".join(a.get("name", "") for a in authors)
            year = re.search(r"(\d{4})", book.get("publish_date", "") or "")
            if year:
                result["year"] = year.group(1)
    except Exception:
        pass

    if not result:
        try:
            resp = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={"q": f"isbn:{code}"},
                timeout=TIMEOUT,
            )
            items = (resp.json() or {}).get("items") or []
            if items:
                info = items[0].get("volumeInfo", {})
                result["title"] = info.get("title", "")
                if info.get("authors"):
                    result["author"] = ", ".join(info["authors"])
                year = re.search(r"(\d{4})", info.get("publishedDate", "") or "")
                if year:
                    result["year"] = year.group(1)
        except Exception:
            pass

    result = _filter_fields(result)
    result["barcode"] = code
    return result


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
