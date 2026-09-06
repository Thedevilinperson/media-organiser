"""Reeksanalyse en waardebepaling van de collectie."""
import threading

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy.orm import joinedload

from extensions import db
from models import Media, MediaType, get_setting
from models_series import SeriesCheck
from security import clean_text, safe_float
from services.jobs import run_series_check
from services.series_analysis import missing_numbers_per_series
from services.value_estimation import estimate_value_lastdodo, search_url

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analyse")

# Profielen waarvoor een reeksanalyse zinvol is.
SERIES_PROFILES = ("strip", "boek")


@analysis_bp.route("/reeksen")
def series():
    filters = {
        "type": request.args.get("type", "").strip(),
        "owner": request.args.get("owner", "").strip(),
        "series": request.args.get("series", "").strip(),
        "author": request.args.get("author", "").strip(),
    }

    all_items = (
        db.session.query(Media)
        .options(joinedload(Media.media_type), joinedload(Media.owner))
        .join(MediaType)
        .filter(MediaType.field_profile.in_(SERIES_PROFILES))
        .filter(Media.series.isnot(None), Media.series_number.isnot(None))
        .all()
    )

    def matches(m, ignore=None):
        if filters["type"] and ignore != "type":
            if not m.media_type or m.media_type.code != filters["type"]:
                return False
        if filters["owner"] and ignore != "owner":
            if not m.owner or m.owner.name != filters["owner"]:
                return False
        if filters["series"] and ignore != "series" and m.series != filters["series"]:
            return False
        if filters["author"] and ignore != "author" and (m.author or "") != filters["author"]:
            return False
        return True

    # Cascaderende keuzelijsten: elke lijst toont enkel wat nog mogelijk is
    # gegeven de andere filters, net als bij de volledige lijst.
    def options(ignore, extract):
        values = set()
        for m in all_items:
            if matches(m, ignore=ignore):
                v = extract(m)
                if v:
                    values.add(v)
        return values

    type_options = sorted(
        options("type", lambda m: (m.media_type.code, m.media_type.label) if m.media_type else None),
        key=lambda pair: pair[1].lower(),
    )
    owner_options = sorted(options("owner", lambda m: m.owner.name if m.owner else None), key=str.lower)
    series_options = sorted(options("series", lambda m: m.series), key=str.lower)
    author_options = sorted(options("author", lambda m: m.author), key=str.lower)

    filtered_items = [m for m in all_items if matches(m)]
    analysis = missing_numbers_per_series(filtered_items)

    checks = {c.series: c for c in db.session.query(SeriesCheck).all()}
    for row in analysis:
        row["check"] = checks.get(row["series"])

    return render_template(
        "series_analysis.html",
        analysis=analysis,
        filters=filters,
        type_options=type_options,
        owner_options=owner_options,
        series_options=series_options,
        author_options=author_options,
        check_running=get_setting("series_check_running") == "1",
    )


@analysis_bp.route("/reeksen/controleer-alles", methods=["POST"])
def series_check_all():
    """
    Start de controle bij De Poort voor alle reeksen op de achtergrond. Draait
    in een aparte thread zodat deze aanvraag meteen terugkeert: met veel
    reeksen en de verplichte pauze tussen aanvragen (zie services/jobs.py)
    kan de volledige controle enkele minuten duren, te lang om een
    browserverzoek op te laten wachten.
    """
    if get_setting("series_check_running") == "1":
        return jsonify({"ok": False, "error": "Er loopt al een controle op de achtergrond."})

    app_obj = current_app._get_current_object()
    threading.Thread(target=run_series_check, args=(app_obj,), daemon=True).start()
    return jsonify({"ok": True})


@analysis_bp.route("/waarde")
def value():
    items = (
        db.session.query(Media)
        .options(joinedload(Media.media_type))
        .order_by(Media.title)
        .all()
    )

    per_type = {}
    for m in items:
        label = m.media_type.label if m.media_type else "Onbekend"
        row = per_type.setdefault(label, {"count": 0, "known_count": 0, "value": 0.0})
        row["count"] += 1
        if m.estimated_value:
            row["known_count"] += 1
            row["value"] += m.estimated_value

    for row in per_type.values():
        row["average"] = row["value"] / row["known_count"] if row["known_count"] else 0.0
        # Ruwe extrapolatie naar de items zonder waarde, zodat het totaal niet
        # structureel te laag oogt. Uitdrukkelijk een indicatie.
        row["extrapolated"] = row["average"] * row["count"]

    total = sum(row["value"] for row in per_type.values())
    total_extrapolated = sum(row["extrapolated"] for row in per_type.values())
    without_value = [m for m in items if not m.estimated_value]

    return render_template(
        "value.html",
        per_type=dict(sorted(per_type.items())),
        total=total,
        total_extrapolated=total_extrapolated,
        without_value=without_value,
    )


@analysis_bp.route("/waarde/schat/<int:media_id>", methods=["POST"])
def value_estimate(media_id):
    """Zoekt een richtprijs en bewaart die meteen bij het item."""
    media = db.get_or_404(Media, media_id)
    result = estimate_value_lastdodo(media.title, media.series)
    if result.get("value"):
        media.estimated_value = result["value"]
        media.value_source = "lastdodo"
        db.session.commit()
    return jsonify(result)


@analysis_bp.route("/waarde/opzoeken", methods=["POST"])
def value_lookup():
    """
    Zoekt een richtprijs op titel en reeks, zonder iets te bewaren. Wordt
    gebruikt door de knop op het invulformulier, waar een item nog geen
    nummer heeft omdat het nog niet opgeslagen is.
    """
    title = clean_text(request.form.get("title"), 300, allow_empty_none=False)
    series = clean_text(request.form.get("series"), 300)
    if not title:
        return jsonify({"ok": False, "error": "Vul eerst een titel in.",
                        "value": None, "url": search_url("")})
    return jsonify(estimate_value_lastdodo(title, series))


@analysis_bp.route("/waarde/<int:media_id>/opslaan", methods=["POST"])
def value_save(media_id):
    """Waarde rechtstreeks vanaf het waardeoverzicht invullen."""
    media = db.get_or_404(Media, media_id)
    value = safe_float(request.form.get("value"), None, 0, 1000000)
    media.estimated_value = value
    media.value_source = "manueel" if value is not None else None
    db.session.commit()
    return jsonify({"ok": True, "value": value})
