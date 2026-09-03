"""
Koppeling met Home Assistant om een waarschuwing te pushen wanneer een
uitgeleend item meer dan 1 maand niet terug is.

Gebruikt de standaard Home Assistant REST API (werkt zowel als de app als
add-on binnen HA draait, als wanneer ze standalone op Windows draait en enkel
naar een HA-instantie ergens op het netwerk praat).
Nodig in Instellingen: HA-URL (bv. http://homeassistant.local:8123) en een
Long-Lived Access Token.
"""
import requests


def push_ha_notification(ha_url, ha_token, title, message, notify_service="notify"):
    """
    Roept een notify-service van Home Assistant aan. Faalt zacht: geeft
    (True, None) of (False, foutmelding) terug in plaats van een exception
    op te gooien, zodat de rest van de applicatie (en de dagelijkse
    achtergrondtaak) blijft doorwerken als HA even niet bereikbaar is.
    """
    if not ha_url or not ha_token:
        return False, "Home Assistant URL of token ontbreekt in Instellingen."

    url = ha_url.rstrip("/") + f"/api/services/notify/{notify_service}"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"},
            json={"title": title, "message": message},
            timeout=8,
        )
        if resp.status_code >= 400:
            return False, f"Home Assistant antwoordde met status {resp.status_code}: {resp.text[:200]}"
        return True, None
    except Exception as exc:
        return False, str(exc)
