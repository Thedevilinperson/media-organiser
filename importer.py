"""Massa-import van media vanuit een Excel-bestand (.xlsx)."""
import pandas as pd

# Kolomnamen in het Excel-bestand -> veldnamen op het Media-model.
COLUMN_MAP = {
    "type": "media_type_code",
    "titel": "title",
    "title": "title",
    "reeks": "series",
    "series": "series",
    "nummer in de reeks": "series_number",
    "series_number": "series_number",
    "auteur": "author",
    "auteur / tekenaar": "author",
    "author": "author",
    "collectie": "collection",
    "nummer in de collectie": "collection_number",
    "nummer van de druk": "print_number",
    "eigenaar": "owner_name",
    "owner": "owner_name",
    "dubbel": "is_duplicate",
    "hardcover": "is_hardcover",
    "staat": "condition",
    "commentaar": "comment",
    "comment": "comment",
    "muzikant": "musician",
    "musician": "musician",
    "jaar": "year",
    "year": "year",
    "taal audio": "audio_language",
    "taal ondertiteling": "subtitle_language",
    "barcode": "barcode",
    "waarde": "estimated_value",
}


def read_import_file(filepath):
    """
    Leest een Excel-bestand in en normaliseert de kolomnamen. Geeft een lijst
    van dicts terug (één per rij), klaar om als Media-records aangemaakt te
    worden. Onbekende kolommen worden genegeerd; onbekende media-types of
    eigenaars worden bij het verwerken aangemaakt.
    """
    df = pd.read_excel(filepath)
    df.columns = [str(c).strip().lower() for c in df.columns]

    records = []
    for _, row in df.iterrows():
        record = {}
        for col, value in row.items():
            field = COLUMN_MAP.get(col)
            if not field:
                continue
            if pd.isna(value):
                continue
            if field in ("is_duplicate", "is_hardcover"):
                value = str(value).strip().lower() in ("1", "true", "ja", "yes", "x")
            record[field] = value
        if record:
            records.append(record)
    return records
