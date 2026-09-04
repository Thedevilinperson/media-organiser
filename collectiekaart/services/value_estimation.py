"""
Richtprijs per item.

LastDodo publiceert cataloguswaarden voor strips, boeken en verzamelobjecten,
maar heeft geen publieke API en beschermt de site tegen geautomatiseerde
aanvragen. Een verzoek vanaf een server krijgt daardoor meestal een 403 terug:
dat is een bewuste blokkade, geen storing, en er valt niet omheen te werken
zonder hun voorwaarden te schenden.

Daarom werkt dit in twee stappen. Er wordt één nette poging gedaan; lukt die
niet, dan krijg je een zoeklink naar LastDodo zodat je de waarde in één klik
zelf kan opzoeken en meteen invullen. De cataloguswaarde blijft sowieso een
richtprijs en geen taxatie.
"""
import re
from urllib.parse import urlencode

import requests

TIMEOUT = 10
SEARCH_BASE = "https://www.lastdodo.nl/nl/search"
PRICE_RE = re.compile(r"€\s?([0-9]{1,4}(?:[.,][0-9]{2}))")

# Een gewone browserkop. Niet om iets te omzeilen, maar omdat een verzoek
# zonder deze velden meteen als ruis behandeld wordt.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
}

BLOCKED_MESSAGE = (
    "LastDodo laat automatisch opzoeken niet toe. Gebruik de zoeklink hiernaast "
    "en vul de waarde zelf in."
)


def build_query(title, series=None):
    return " ".join(part for part in (series, title) if part).strip()


def search_url(title, series=None):
    """De zoekpagina van LastDodo waar de gebruiker zelf kan kijken."""
    query = build_query(title, series)
    return SEARCH_BASE + "?" + urlencode({"q": query}) if query else SEARCH_BASE


def estimate_value_lastdodo(title, series=None):
    query = build_query(title, series)
    url = search_url(title, series)
    if not query:
        return {"ok": False, "error": "Geen titel om op te zoeken.", "value": None, "url": url}

    try:
        resp = requests.get(SEARCH_BASE, params={"q": query}, timeout=TIMEOUT, headers=HEADERS)
    except Exception as exc:
        return {"ok": False, "error": f"LastDodo is niet bereikbaar ({exc}).", "value": None, "url": url}

    if resp.status_code in (401, 403, 429) or "Checking your browser" in resp.text[:4000]:
        return {"ok": False, "error": BLOCKED_MESSAGE, "value": None, "url": url}
    if resp.status_code >= 400:
        return {"ok": False, "error": f"LastDodo antwoordde met status {resp.status_code}.",
                "value": None, "url": url}

    prices = []
    for match in PRICE_RE.finditer(resp.text):
        try:
            prices.append(float(match.group(1).replace(",", ".")))
        except ValueError:
            continue

    # Alleen realistische bedragen, en de mediaan in plaats van de eerste
    # treffer: dat is minder gevoelig voor een uitschieter of voor een prijs
    # die ergens anders op de pagina staat.
    prices = sorted(p for p in prices if 0.5 <= p <= 2000)
    if not prices:
        return {"ok": False, "error": "Geen richtprijs gevonden op de zoekpagina.",
                "value": None, "url": url}

    return {"ok": True, "error": None, "value": round(prices[len(prices) // 2], 2), "url": url}
