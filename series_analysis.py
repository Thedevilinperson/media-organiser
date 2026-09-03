"""
Analyse van reeksen: ontbrekende nummers binnen de eigen collectie, en een
best-effort controle op nieuwe/ontbrekende nummers via een externe website
(bv. De Poort) voor strips.

De ontbrekende-nummers-berekening op basis van de eigen collectie gebeurt
volledig lokaal met eenvoudige wiskunde: geen AI en geen internet nodig.

De controle op "is er een nieuw nummer uitgekomen dat ik nog niet heb" vereist
gegevens van buiten de eigen collectie. Dit kan zonder AI door de catalogus-
pagina van een website zoals De Poort te doorzoeken (webscraping). Dat is wél
afhankelijk van de structuur van die website: als de site haar HTML wijzigt,
moet de "parse_depoort_series"-functie hieronder bijgewerkt worden. Er wordt
bewust geen AI/LLM gebruikt voor deze stap, aangezien de benodigde informatie
(een lijst van nummers per reeks) rechtstreeks uit de paginastructuur te halen
is.
"""
import re
from collections import defaultdict

import requests
from bs4 import BeautifulSoup


def missing_numbers_per_series(media_items):
    """
    Geeft per reeks (van strips/boeken) de ontbrekende nummers in de eigen
    collectie terug, o.b.v. het laagste tot het hoogste nummer dat je bezit.

    media_items: lijst van Media-objecten (al gefilterd op profiel strip/boek)
    Return: lijst van dicts {series, owned, missing, highest_owned}
    """
    by_series = defaultdict(set)
    for m in media_items:
        if not m.series:
            continue
        if m.series_number is None:
            continue
        by_series[m.series].add(m.series_number)

    result = []
    for series, numbers in sorted(by_series.items()):
        numbers = sorted(numbers)
        lowest, highest = numbers[0], numbers[-1]
        # enkel gehele nummers controleren op gaten (specials met .5 e.d. overslaan)
        int_numbers = {n for n in numbers if float(n).is_integer()}
        if int_numbers:
            full_range = set(range(int(min(int_numbers)), int(max(int_numbers)) + 1))
            missing = sorted(full_range - int_numbers)
        else:
            missing = []
        result.append(
            {
                "series": series,
                "owned": numbers,
                "missing": missing,
                "highest_owned": highest,
            }
        )
    return result


def parse_depoort_series(html, series_name):
    """
    Best-effort parser voor een De Poort catalogus-pagina van een reeks.
    Verwacht een lijst van productkaarten met daarin een titel die het
    volgnummer van het album bevat (bv. "Reeksnaam - T12 Titel").

    LET OP: dit is een best-effort implementatie. De Poort kan de opbouw van
    hun pagina's op elk moment wijzigen, waardoor deze selectors niet meer
    kloppen. Test en pas de CSS-selectors hieronder aan indien nodig.
    """
    soup = BeautifulSoup(html, "html.parser")
    numbers = set()
    # Typische PrestaShop-opbouw (De Poort draait op PrestaShop): productnaam
    # zit meestal in een element met class "product-title" of "h3".
    candidates = soup.select(".product-title, h3, .product-name, a[title]")
    number_pattern = re.compile(r"\bT(?:ome)?\.?\s*(\d+)\b|\bn[°o]\s*(\d+)\b|#\s*(\d+)\b", re.I)
    for el in candidates:
        text = el.get("title") or el.get_text(" ", strip=True)
        if not text:
            continue
        match = number_pattern.search(text)
        if match:
            num = next(g for g in match.groups() if g)
            numbers.add(int(num))
    return sorted(numbers)


def check_new_releases(series_name, owned_numbers, base_url=None, timeout=10):
    """
    Probeert via De Poort te bepalen of er nieuwe nummers van een reeks
    bestaan die niet in de eigen collectie zitten. Geeft een dict terug met
    status en resultaat. Faalt zacht (geen exception naar buiten) zodat de
    rest van de applicatie blijft werken als het internet of de site niet
    bereikbaar is.
    """
    if base_url is None:
        base_url = "https://depoort.com/nl/recherche?controller=search&s=" + series_name.replace(" ", "+")
    try:
        resp = requests.get(base_url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as exc:  # netwerk, timeout, DNS, ...
        return {"ok": False, "error": str(exc), "new_numbers": []}

    try:
        found_numbers = parse_depoort_series(resp.text, series_name)
    except Exception as exc:
        return {"ok": False, "error": f"kon pagina niet verwerken: {exc}", "new_numbers": []}

    new_numbers = sorted(set(found_numbers) - set(int(n) for n in owned_numbers if float(n).is_integer()))
    return {"ok": True, "error": None, "new_numbers": new_numbers, "site_numbers": found_numbers}
