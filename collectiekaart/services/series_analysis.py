"""
Reeksanalyse.

Deel 1 (ontbrekende nummers in je eigen collectie) is pure wiskunde: volledig
lokaal, geen internet en geen AI.

Deel 2 (bestaan er nieuwere nummers die je nog niet hebt?) heeft gegevens van
buiten je collectie nodig. Dat kan zonder AI door de catalogus van De Poort te
doorzoeken en de volgnummers uit de productnamen te halen. Die aanpak hangt
wel af van de opbouw van hun website: wijzigt die, dan moet parse_series_page
hieronder bijgewerkt worden. Alles faalt zacht, met een nette melding.
"""
import re
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

DEPOORT_SEARCH = "https://depoort.com/nl/zoeken"
NUMBER_PATTERN = re.compile(r"\b(?:T(?:ome)?\.?|deel|nr\.?|n[°o]|#)\s*(\d{1,3})\b", re.I)


def missing_numbers_per_series(media_items):
    """
    Geeft per reeks de ontbrekende nummers terug tussen het laagste en het
    hoogste nummer dat je bezit. Halve nummers (specials als 3.5) tellen mee
    als bezit, maar worden niet als gat gerekend.
    """
    by_series = defaultdict(set)
    for m in media_items:
        if m.series and m.series_number is not None:
            by_series[m.series].add(m.series_number)

    result = []
    for series, numbers in sorted(by_series.items(), key=lambda kv: kv[0].lower()):
        numbers = sorted(numbers)
        whole = {int(n) for n in numbers if float(n).is_integer()}
        missing = sorted(set(range(min(whole), max(whole) + 1)) - whole) if whole else []
        result.append({
            "series": series,
            "owned": [int(n) if float(n).is_integer() else n for n in numbers],
            "missing": missing,
            "highest_owned": int(numbers[-1]) if float(numbers[-1]).is_integer() else numbers[-1],
            "count": len(numbers),
        })
    return result


def compact_ranges(numbers):
    """
    Schrijft een lijst nummers compact: [4, 9, 10, 11, 12, 13] wordt
    "4, 9–13". Twee opeenvolgende nummers blijven los ("1, 2"), vanaf drie
    wordt het een bereik. Zonder dit kon één reeks met honderden ontbrekende
    nummers een tabelcel zo breed maken dat de kolommen ernaast buiten beeld
    vielen.
    """
    values = sorted({int(n) for n in (numbers or []) if float(n).is_integer()})
    if not values:
        return ""
    parts = []
    start = prev = values[0]
    for n in values[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        if prev == start:
            parts.append(str(start))
        elif prev == start + 1:
            parts.append(f"{start}, {prev}")
        else:
            parts.append(f"{start}–{prev}")
        if n is not None:
            start = prev = n
    return ", ".join(parts)


def parse_series_page(html):
    """
    Best-effort parser voor een catalogus- of zoekpagina van De Poort.
    De site draait op PrestaShop; productnamen staan meestal in een element
    met class 'product-title' of in een titel-attribuut, in de vorm
    'Reeksnaam - T12 Albumtitel'.

    Wijzigt De Poort de opbouw van de pagina, dan moeten enkel de selectors
    en het patroon hieronder aangepast worden.
    """
    soup = BeautifulSoup(html, "html.parser")
    numbers = set()
    for el in soup.select(".product-title, .product-name, h2 a, h3 a, a[title]"):
        text = el.get("title") or el.get_text(" ", strip=True)
        if not text:
            continue
        match = NUMBER_PATTERN.search(text)
        if match:
            try:
                numbers.add(int(match.group(1)))
            except ValueError:
                continue
    return sorted(numbers)


def check_new_releases(series_name, owned_numbers, timeout=10):
    """
    Kijkt of er nummers van een reeks bestaan die nog niet in je collectie
    zitten. Faalt zacht: bij netwerkproblemen of een gewijzigde website komt
    er een foutmelding terug in plaats van een uitzondering.
    """
    series_name = (series_name or "").strip()
    if not series_name:
        return {"ok": False, "error": "Geen reeksnaam opgegeven.", "new_numbers": []}

    try:
        resp = requests.get(
            DEPOORT_SEARCH,
            params={"controller": "search", "s": series_name},
            timeout=timeout,
            headers={"User-Agent": "Collectiekaart/0.1"},
        )
        resp.raise_for_status()
    except Exception as exc:
        return {"ok": False, "error": f"Website niet bereikbaar ({exc}).", "new_numbers": []}

    try:
        found = parse_series_page(resp.text)
    except Exception as exc:
        return {"ok": False, "error": f"Kon de pagina niet verwerken ({exc}).", "new_numbers": []}

    if not found:
        return {
            "ok": True,
            "error": None,
            "new_numbers": [],
            "site_numbers": [],
            "note": "Geen nummers herkend op de website. Mogelijk is de reeksnaam anders geschreven "
                    "of is de opbouw van de site gewijzigd.",
        }

    owned = {int(n) for n in owned_numbers if float(n).is_integer()}
    return {
        "ok": True,
        "error": None,
        "new_numbers": sorted(set(found) - owned),
        "site_numbers": found,
        "note": None,
    }
