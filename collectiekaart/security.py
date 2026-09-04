"""
Beveiligingslaag: CSRF-bescherming, veilige headers en invoervalidatie.

Zie SECURITY.md voor de volledige screening van de code op kwetsbaarheden
(vereiste 3a).
"""
import hmac
import os
import re
import secrets

from flask import abort, request, session

from version import __version__

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Alles wat de gebruiker als eigen veldnaam of mediatypecode ingeeft, wordt
# hierop gecontroleerd. Zo kan er geen rare sleutel in de JSON-kolom of in
# een formuliernaam terechtkomen.
SAFE_KEY_RE = re.compile(r"^[a-z0-9_]{1,50}$")


def generate_csrf():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def valid_key(value):
    return bool(SAFE_KEY_RE.match(value or ""))


def safe_float(value, default=None, minimum=None, maximum=None):
    """Zet tekst om naar een float zonder ooit een 500-fout te veroorzaken."""
    if value is None:
        return default
    text = str(value).strip().replace(",", ".")
    if not text:
        return default
    try:
        number = float(text)
    except (TypeError, ValueError):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number


def safe_int(value, default=None, minimum=None, maximum=None):
    number = safe_float(value, None)
    if number is None:
        return default
    number = int(number)
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number


def clean_text(value, max_length=300, allow_empty_none=True):
    """Trimt en begrenst vrije tekst; voorkomt overdreven lange invoer."""
    text = (value or "").strip()
    if len(text) > max_length:
        text = text[:max_length]
    if not text and allow_empty_none:
        return None
    return text


def register_security(app):
    @app.before_request
    def _csrf_protect():
        if request.method in SAFE_METHODS:
            return
        token = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("_csrf", "")
        if not expected or not token or not hmac.compare_digest(str(token), str(expected)):
            abort(400, description="Ongeldig of ontbrekend CSRF-token. Herlaad de pagina en probeer opnieuw.")

    @app.context_processor
    def _inject_globals():
        return {"csrf_token": generate_csrf, "app_version": __version__}

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        # Geen 'unsafe-inline' voor scripts: alle JavaScript staat in
        # aparte bestanden onder /static/js. 'frame-ancestors' wordt bewust
        # NIET beperkt, anders kan Home Assistant de add-on niet in een
        # iframe (Ingress) tonen.
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' https://cdnjs.cloudflare.com; "
            "connect-src 'self'; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'",
        )
        return resp


def allowed_image(filename, allowed_extensions):
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in allowed_extensions


def unique_filename(original, upload_dir):
    """
    Bouwt een nieuwe bestandsnaam op uit een willekeurig token plus de
    (gecontroleerde) extensie. De originele naam wordt bewust niet
    hergebruikt, zodat padmanipulatie of dubbele extensies geen kans krijgen.
    """
    ext = original.rsplit(".", 1)[1].lower()
    name = f"{secrets.token_hex(12)}.{ext}"
    return name, os.path.join(upload_dir, name)
