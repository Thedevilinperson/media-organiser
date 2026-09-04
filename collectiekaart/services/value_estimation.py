"""
Waardebepaling per item.

Lastdodo publiceert richtprijzen voor strips en verzamelobjecten. Er is geen
publieke API, dus dit gebeurt met best-effort scraping: gratis, zonder AI,
maar gevoelig voor wijzigingen aan hun website. Vindt de app niets
betrouwbaars, dan blijft het veld leeg en vul je de waarde manueel in.

Dit is uitdrukkelijk een richtprijs en geen taxatie.
"""
import re

import requests

TIMEOUT = 10
PRICE_RE = re.compile(r"€\s?([0-9]{1,4}(?:[.,][0-9]{2}))")


def estimate_value_lastdodo(title, series=None):
    query = " ".join(part for part in (series, title) if part).strip()
    if not query:
        return {"ok": False, "error": "Geen titel om op te zoeken.", "value": None}

    try:
        resp = requests.get(
            "https://www.lastdodo.nl/nl/search",
            params={"q": query},
            timeout=TIMEOUT,
            headers={"User-Agent": "Collectiekaart/0.1"},
        )
        resp.raise_for_status()
    except Exception as exc:
        return {"ok": False, "error": f"Website niet bereikbaar ({exc}).", "value": None}

    prices = []
    for match in PRICE_RE.finditer(resp.text):
        try:
            prices.append(float(match.group(1).replace(",", ".")))
        except ValueError:
            continue

    # Alleen realistische bedragen, en de mediaan in plaats van de eerste
    # treffer: dat is minder gevoelig voor een uitschieter of een prijs die
    # ergens anders op de pagina staat.
    prices = sorted(p for p in prices if 0.5 <= p <= 2000)
    if not prices:
        return {"ok": True, "error": "Geen richtprijs gevonden.", "value": None}

    median = prices[len(prices) // 2]
    return {"ok": True, "error": None, "value": round(median, 2)}
