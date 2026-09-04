"""
Configuratie en padbepaling.

Alle schrijfbare paden komen uit omgevingsvariabelen zodat dezelfde code
werkt op Windows (naast het script) en in een Home Assistant add-on
(persistente /data-map). Zo zijn er geen symlinks of containertrucs nodig.
"""
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.environ.get("COLLECTIEKAART_DATA_DIR") or os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.environ.get("COLLECTIEKAART_UPLOAD_DIR") or os.path.join(BASE_DIR, "uploads")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _secret_key():
    """
    Haalt de sessiesleutel uit de omgeving, of maakt er eenmalig een aan en
    bewaart die in de datamap. Zo staat er nooit een hardgecodeerde sleutel
    in de broncode (zie SECURITY.md, bevinding B1).
    """
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    key_path = os.path.join(DATA_DIR, "secret.key")
    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as fh:
            key = fh.read().strip()
            if key:
                return key

    key = secrets.token_urlsafe(48)
    with open(key_path, "w", encoding="utf-8") as fh:
        fh.write(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass  # Windows/FAT ondersteunt dit niet altijd
    return key


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(DATA_DIR, "collectiekaart.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SECRET_KEY = _secret_key()

    # Uploadlimiet: beschermt tegen het volpompen van de schijf.
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    UPLOAD_DIR = UPLOAD_DIR
    DATA_DIR = DATA_DIR

    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    # Kaftfoto's worden bij het opslaan verkleind: scheelt schijfruimte en
    # laadtijd op een smartphone (vereiste 3c).
    COVER_MAX_PIXELS = 900
