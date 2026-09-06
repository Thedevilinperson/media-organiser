"""Overzicht, volledige lijst, handleiding en het uitserveren van kaftfoto's."""
import os

from flask import Blueprint, current_app, render_template, request, send_from_directory
from sqlalchemy.orm import joinedload

from extensions import db
from models import CustomField, Media, MediaType
from views.main_helpers import group_by_type, matches_filters, matches_search, sort_key

main_bp = Blueprint("main", __name__)

# Kolommen van de volledige lijst, in weergavevolgorde. key=None betekent dat
# de kolom altijd getoond wordt (geen veld met een eigen aan/uit-instelling);
# een echte key wordt enkel getoond als minstens één van de mediatypes die in
# de huidige resultaten voorkomen, dat veld zichtbaar heeft staan. Zo krijg je
# bij bv. enkel cd's niet meer alle vierentwintig kolommen te zien, maar enkel
# wat voor een cd van toepassing is.
FULL_LIST_COLUMNS = [
    ("cover_image", "Kaft"),
    (None, "Type"),
    ("series", "Reeks"),
    ("series_number", "Nr."),
    (None, "Titel"),
    ("author", "Auteur"),
    ("musician", "Muzikant"),
    ("collection", "Collectie"),
    ("collection_number", "Nr. coll."),
    ("print_number", "Druk"),
    ("is_hardcover", "Hardcover"),
    ("is_duplicate", "Dubbel"),
    ("condition", "Staat"),
    ("owner_id", "Eigenaar"),
    ("year", "Jaar"),
    ("audio_language", "Taal audio"),
    ("subtitle_language", "Ondertiteling"),
    ("barcode", "Barcode"),
    ("estimated_value", "Waarde"),
]


def _all_media():
    """
    Eén query met eager loading in plaats van een aparte query per rij voor
    type, eigenaar en uitleningen (vereiste 3c).
    """
    return (
        db.session.query(Media)
        .options(
            joinedload(Media.media_type),
            joinedload(Media.owner),
            joinedload(Media.loans),
        )
        .all()
    )


def _totals(items):
    totals = {}
    for media in items:
        label = media.media_type.label if media.media_type else "Onbekend"
        totals[label] = totals.get(label, 0) + 1
    return sorted(totals.items())


def _visible_field_keys(items):
    """
    Unie van de zichtbare velden van alle mediatypes die in `items`
    voorkomen, zodat de volledige lijst geen kolommen toont die voor geen
    enkel getoond type gebruikt worden. Bij een leeg resultaat (bv. een
    zoekterm die niets oplevert) vallen we terug op alle bestaande types,
    zodat de kolomkoppen niet zomaar verdwijnen.
    """
    types_present = {m.media_type for m in items if m.media_type}
    if not types_present:
        types_present = set(db.session.query(MediaType).all())
    visible = set()
    for media_type in types_present:
        visible |= media_type.visible_fields()
    return visible


@main_bp.route("/")
def index():
    """
    Het overzicht: kort en leesbaar op een telefoon. Per type alleen de
    kolommen die er voor dat type toe doen, en alleen een zoekbalk. De
    filters staan op de volledige lijst, zodat je hier meteen resultaten
    ziet in plaats van eerst langs vier keuzelijsten te moeten scrollen.
    """
    q = request.args.get("q", "").strip()[:100]
    all_items = _all_media()
    found = [m for m in all_items if matches_search(m, q)]

    return render_template(
        "index.html",
        groups=group_by_type(found),
        totals=_totals(all_items),
        grand_total=len(all_items),
        shown=len(found),
        q=q,
    )


@main_bp.route("/lijst")
def full_list():
    """
    De volledige lijst met de cascaderende filters. Toont per resultaat enkel
    de velden die bij de aanwezige mediatypes horen (vereiste: geen
    ongebruikte kolommen), zodat bv. filteren op één type de tabel meteen
    smaller maakt.
    """
    filters = {
        "type": request.args.get("type", "").strip(),
        "owner": request.args.get("owner", "").strip(),
        "series": request.args.get("series", "").strip(),
        "title": request.args.get("title", "").strip(),
    }
    q = request.args.get("q", "").strip()[:100]

    all_items = _all_media()
    found = [m for m in all_items if matches_search(m, q)]
    items = sorted((m for m in found if matches_filters(m, filters)), key=sort_key)

    # Cascaderende keuzelijsten: elke lijst toont enkel wat nog mogelijk is
    # gegeven de andere filters (vereiste 1.a).
    def options(ignore, extract):
        values = set()
        for media in found:
            if matches_filters(media, filters, ignore=ignore):
                value = extract(media)
                if value:
                    values.add(value)
        return values

    type_options = sorted(
        options("type", lambda m: (m.media_type.code, m.media_type.label) if m.media_type else None),
        key=lambda pair: pair[1],
    )

    # Welke velden en eigen velden effectief getoond worden, afgeleid uit de
    # mediatypes die in `items` voorkomen.
    visible_fields = _visible_field_keys(items)
    type_ids_present = {m.media_type_id for m in items}

    all_custom_fields = db.session.query(CustomField).order_by(CustomField.label).all()
    custom_fields = [
        f for f in all_custom_fields
        if f.media_type_id is None or f.media_type_id in type_ids_present
    ]

    columns = [(key, label) for key, label in FULL_LIST_COLUMNS if key is None or key in visible_fields]
    show_comment = "comment" in visible_fields
    # +1 voor "Uitgeleend", +1 voor de kolom met de actieknoppen.
    column_count = len(columns) + len(custom_fields) + (1 if show_comment else 0) + 2

    return render_template(
        "full_list.html",
        items=items,
        totals=_totals(all_items),
        grand_total=len(all_items),
        q=q,
        filters=filters,
        type_options=type_options,
        owner_options=sorted(options("owner", lambda m: m.owner.name if m.owner else None), key=str.lower),
        series_options=sorted(options("series", lambda m: m.series), key=str.lower),
        title_options=sorted(options("title", lambda m: m.title), key=str.lower),
        custom_fields=custom_fields,
        columns=columns,
        visible_fields=visible_fields,
        show_comment=show_comment,
        column_count=column_count,
    )


@main_bp.route("/handleiding")
def manual():
    """Handleiding rechtstreeks in de applicatie (vereiste 4b)."""
    return render_template("handleiding.html")


@main_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """
    Serveert kaftfoto's. Ze staan bewust buiten de statische map, omdat ze in
    Home Assistant in /data terechtkomen. send_from_directory blokkeert
    padmanipulatie zoals '../../etc/passwd'.
    """
    return send_from_directory(
        os.path.abspath(current_app.config["UPLOAD_DIR"]),
        filename,
        max_age=86400,
    )
