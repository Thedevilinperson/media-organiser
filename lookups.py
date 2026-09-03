"""
Externe opzoekfuncties:
  1. Barcode (ISBN/EAN) -> boek-/albumgegevens, zonder AI (Open Library + Google Books, beide gratis en zonder key).
  2. Foto-analyse -> automatisch invullen van velden vanaf een omslagfoto.
     - Zonder AI: OCR met tesseract leest de tekst op de kaft (titel/reeks is dan een gok op basis van de grootste tekstregel).
     - Met AI (optioneel, enkel als de gebruiker in Instellingen een API-key instelt):
       de foto wordt naar een vision-model gestuurd dat titel/reeks/nummer/auteur herkent.
  3. Collectiewaarde -> schatting per item, met Lastdodo als voorbeeldbron (best-effort scraping).
"""
import base64
import io
import re

import requests

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


# ---------------------------------------------------------------------------
# 1. Barcode lookup (geen AI nodig)
# ---------------------------------------------------------------------------
def lookup_barcode(code):
    """
    Zoekt een ISBN/EAN op via gratis, key-loze bronnen. Werkt goed voor boeken
    (ISBN-13). Voor strips/comics/manga is de dekking wisselend omdat niet elke
    uitgeverij een ISBN op de kaft plaatst; ontbrekende velden kunnen dan nog
    manueel aangevuld worden zoals in de vereisten gevraagd wordt.
    Retourneert een dict met de velden die gevonden zijn, of {} indien niets.
    """
    code = re.sub(r"[^0-9Xx]", "", code or "")
    if not code:
        return {}

    result = {}

    # Open Library (gratis, geen key)
    try:
        resp = requests.get(
            "https://openlibrary.org/api/books",
            params={"bibkeys": f"ISBN:{code}", "format": "json", "jscmd": "data"},
            timeout=8,
        )
        data = resp.json()
        book = data.get(f"ISBN:{code}")
        if book:
            result["title"] = book.get("title", "")
            authors = book.get("authors") or []
            if authors:
                result["author"] = ", ".join(a.get("name", "") for a in authors)
            publish_date = book.get("publish_date", "")
            year_match = re.search(r"(\d{4})", publish_date or "")
            if year_match:
                result["year"] = int(year_match.group(1))
    except Exception:
        pass

    # Google Books als aanvulling/fallback (gratis, geen key nodig voor basisopzoekingen)
    if not result:
        try:
            resp = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={"q": f"isbn:{code}"},
                timeout=8,
            )
            data = resp.json()
            items = data.get("items") or []
            if items:
                info = items[0].get("volumeInfo", {})
                result["title"] = info.get("title", "")
                if info.get("authors"):
                    result["author"] = ", ".join(info["authors"])
                published = info.get("publishedDate", "")
                year_match = re.search(r"(\d{4})", published or "")
                if year_match:
                    result["year"] = int(year_match.group(1))
        except Exception:
            pass

    result["barcode"] = code
    return result


# ---------------------------------------------------------------------------
# 2. Foto-analyse
# ---------------------------------------------------------------------------
def analyze_cover_ocr(image_path):
    """
    Leest tekst van de kaft met lokale OCR (tesseract), zonder AI en zonder
    internet. Dit is een ruwe gok: de langste/grootste tekstregel wordt als
    titel voorgesteld. Werkt het best bij een scherpe, rechte foto van de
    voorkant.
    """
    if not OCR_AVAILABLE:
        return {"ok": False, "error": "OCR (tesseract/pillow) is niet beschikbaar op deze installatie.", "fields": {}}
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="nld+eng+fra")
    except Exception as exc:
        return {"ok": False, "error": f"OCR mislukt: {exc}", "fields": {}}

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return {"ok": True, "error": None, "fields": {}, "raw_text": text}

    # Ruwe heuristiek: langste regel = titel-kandidaat.
    title_guess = max(lines, key=len)
    fields = {"title": title_guess}
    return {"ok": True, "error": None, "fields": fields, "raw_text": text}


def analyze_cover_ai(image_path, api_key, model="claude-sonnet-4-6"):
    """
    Stuurt de omslagfoto naar een vision-model (Anthropic API) om titel,
    reeks, nummer en auteur/tekenaar te laten herkennen. Wordt enkel gebruikt
    als de gebruiker zelf een API-key heeft ingesteld in Instellingen -
    zonder key wordt deze functie niet aangeroepen en valt de applicatie
    terug op de OCR-methode hierboven.

    Werkt ook met een lokaal draaiend LLM met een Anthropic- of OpenAI-
    compatibele API: pas 'base_url' aan naar het lokale endpoint.
    """
    if not api_key:
        return {"ok": False, "error": "Geen AI API-key ingesteld.", "fields": {}}

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    media_type = "image/jpeg"
    if image_path.lower().endswith(".png"):
        media_type = "image/png"

    prompt = (
        "Dit is een foto van de kaft van een strip, boek, cd of dvd. "
        "Geef ENKEL een JSON-object terug (geen uitleg, geen markdown) met de "
        "velden die je kan herkennen uit: title, series, series_number, author, "
        "year, musician. Laat velden die je niet zeker weet gewoon weg."
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        raw = "\n".join(text_blocks).strip()
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        import json as _json
        fields = _json.loads(raw)
        return {"ok": True, "error": None, "fields": fields}
    except Exception as exc:
        return {"ok": False, "error": f"AI-analyse mislukt: {exc}", "fields": {}}


# ---------------------------------------------------------------------------
# 3. Collectiewaarde (best-effort, bv. Lastdodo)
# ---------------------------------------------------------------------------
def estimate_value_lastdodo(title, series=None):
    """
    Best-effort opzoeking van een richtprijs op Lastdodo. Zoals bij De Poort
    geldt: dit scraped publieke zoekresultaten en is gevoelig voor wijzigingen
    aan de website. Geeft None terug als er niets betrouwbaars gevonden wordt
    (bv. omdat de site niet bereikbaar is vanaf de server) - de gebruiker kan
    de waarde dan nog altijd manueel invullen.
    """
    query = f"{series} {title}".strip() if series else title
    try:
        resp = requests.get(
            "https://www.lastdodo.com/nl/search",
            params={"q": query},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "value": None}

    price_match = re.search(r"€\s?([0-9]+[.,][0-9]{2})", resp.text)
    if price_match:
        value = float(price_match.group(1).replace(",", "."))
        return {"ok": True, "error": None, "value": value}
    return {"ok": True, "error": "geen prijs gevonden op de pagina", "value": None}
