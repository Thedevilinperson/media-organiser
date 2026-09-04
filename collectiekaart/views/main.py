"""Basisweergave, handleiding en het uitserveren van kaftfoto's."""
import os

from flask import Blueprint, current_app, render_template, request, send_from_directory
from sqlalchemy.orm import joinedload

from extensions import db
from models import Media
from views.main_helpers import matches_filters, matches_search, sort_key

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    filters = {
        "type": request.args.get("type", "").strip(),
        "owner": request.args.get("owner", "").strip(),
        "series": request.args.get("series", "").strip(),
        "title": request.args.get("title", "").strip(),
    }
    q = request.args.get("q", "").strip()[:100]

    # Eén enkele query met eager loading in plaats van vijf aparte queries
    # plus een N+1 per rij voor type/eigenaar/uitlening. Voor een persoonlijke
    # collectie is dat merkbaar zuiniger (vereiste 3c).
    all_items = (
        db.session.query(Media)
        .options(
            joinedload(Media.media_type),
            joinedload(Media.owner),
            joinedload(Media.loans),
        )
        .all()
    )

    found = [m for m in all_items if matches_search(m, q)]
    items = sorted((m for m in found if matches_filters(m, filters)), key=sort_key)

    # Cascaderende keuzelijsten: elke lijst toont enkel wat nog mogelijk is
    # gegeven de andere filters (vereiste 1.a).
    def options(ignore, extract):
        values = set()
        for m in found:
            if matches_filters(m, filters, ignore=ignore):
                value = extract(m)
                if value:
                    values.add(value)
        return values

    type_options = sorted(
        options("type", lambda m: (m.media_type.code, m.media_type.label) if m.media_type else None),
        key=lambda pair: pair[1],
    )
    owner_options = sorted(options("owner", lambda m: m.owner.name if m.owner else None), key=str.lower)
    series_options = sorted(options("series", lambda m: m.series), key=str.lower)
    title_options = sorted(options("title", lambda m: m.title), key=str.lower)

    # Totaal per mediatype over de volledige collectie (vereiste 1.a.iii).
    totals = {}
    for m in all_items:
        label = m.media_type.label if m.media_type else "Onbekend"
        totals[label] = totals.get(label, 0) + 1

    return render_template(
        "index.html",
        items=items,
        totals=sorted(totals.items()),
        grand_total=len(all_items),
        q=q,
        filters=filters,
        type_options=type_options,
        owner_options=owner_options,
        series_options=series_options,
        title_options=title_options,
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
