"""
Koppeling met Home Assistant: pusht een melding als een item langer dan een
maand uitgeleend is.

Werkt zowel wanneer de app als add-on binnen HA draait als wanneer ze
standalone op Windows staat en enkel over het netwerk met HA praat. Nodig in
Instellingen: de HA-URL en een Long-Lived Access Token.
"""
import requests

TIMEOUT = 8


def push_ha_notification(ha_url, ha_token, title, message, notify_service="persistent_notification"):
    """
    Roept een notify-service van Home Assistant aan. Faalt zacht: geeft
    (True, None) of (False, foutmelding) terug in plaats van een uitzondering
    op te gooien, zodat de dagelijkse achtergrondtaak blijft doorlopen als HA
    even niet bereikbaar is.
    """
    if not ha_url or not ha_token:
        return False, "Home Assistant URL of token ontbreekt in Instellingen."
    if not ha_url.startswith(("http://", "https://")):
        return False, "Home Assistant URL moet met http:// of https:// beginnen."

    url = ha_url.rstrip("/") + f"/api/services/notify/{notify_service}"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"},
            json={"title": title, "message": message},
            timeout=TIMEOUT,
        )
        if resp.status_code >= 400:
            return False, f"Home Assistant antwoordde met status {resp.status_code}."
        return True, None
    except Exception as exc:
        return False, str(exc)


def test_connection(ha_url, ha_token):
    """Snelle test vanuit Instellingen: klopt de URL en het token?"""
    if not ha_url or not ha_token:
        return False, "Vul eerst een URL en een token in."
    if not ha_url.startswith(("http://", "https://")):
        return False, "De URL moet met http:// of https:// beginnen."
    try:
        resp = requests.get(
            ha_url.rstrip("/") + "/api/",
            headers={"Authorization": f"Bearer {ha_token}"},
            timeout=TIMEOUT,
        )
    except Exception as exc:
        return False, str(exc)
    if resp.status_code == 200:
        return True, "Verbinding met Home Assistant is in orde."
    if resp.status_code in (401, 403):
        return False, "Het token wordt geweigerd door Home Assistant."
    return False, f"Onverwachte status {resp.status_code}."
