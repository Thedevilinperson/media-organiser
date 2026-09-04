"""Verkleinen en veilig opslaan van kaftfoto's."""

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:  # pragma: no cover
    PIL_AVAILABLE = False


def save_cover(file_storage, target_path, max_pixels=900):
    """
    Slaat een geuploade kaftfoto op en verkleint ze tot max_pixels aan de
    langste zijde. Dat scheelt schijfruimte en laadtijd op een telefoon
    (vereiste 3c). Lukt het verkleinen niet, dan blijft het bestand staan
    zoals het is.

    Het openen met Pillow werkt meteen als validatie: een bestand dat
    'kaft.jpg' heet maar geen echte afbeelding is, wordt hier geweigerd.
    """
    file_storage.save(target_path)
    if not PIL_AVAILABLE:
        return True, None
    try:
        with Image.open(target_path) as img:
            img.verify()  # controleert of het echt een afbeelding is
        with Image.open(target_path) as img:
            if img.mode in ("P", "RGBA", "LA"):
                img = img.convert("RGB")
            img.thumbnail((max_pixels, max_pixels))
            img.save(target_path, quality=82, optimize=True)
        return True, None
    except Exception as exc:
        return False, f"Geen geldige afbeelding: {exc}"
