"""Overzicht, volledige lijst, handleiding en het uitserveren van kaftfoto's."""
import os

from flask import Blueprint, current_app, render_template, request, send_from_directory
from sqlalchemy.orm import joinedload

from extensions import db
from models import CustomField, Media
from views.main_helpers import group_by_type, matches_filters, matches_search, sort_key

main_bp = Blueprint("main", __name__)


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
    """De volledige lijst met alle velden, plus de cascaderende filters."""
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

    custom_fields = db.session.query(CustomField).order_by(CustomField.label).all()

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
