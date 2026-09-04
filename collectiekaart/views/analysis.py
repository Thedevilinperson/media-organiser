"""Reeksanalyse en waardebepaling van de collectie."""
from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.orm import joinedload

from extensions import db
from models import Media, MediaType
from security import safe_float
from services.series_analysis import check_new_releases, missing_numbers_per_series
from services.value_estimation import estimate_value_lastdodo

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analyse")

# Profielen waarvoor een reeksanalyse zinvol is.
SERIES_PROFILES = ("strip", "boek")


@analysis_bp.route("/reeksen")
def series():
    items = (
        db.session.query(Media)
        .join(MediaType)
        .filter(MediaType.field_profile.in_(SERIES_PROFILES))
        .filter(Media.series.isnot(None), Media.series_number.isnot(None))
        .all()
    )
    return render_template("series_analysis.html", analysis=missing_numbers_per_series(items))


@analysis_bp.route("/reeksen/nieuw", methods=["POST"])
def series_check_new():
    series_name = (request.form.get("series") or "").strip()[:200]
    owned = [n for n in (safe_float(v) for v in request.form.getlist("owned")) if n is not None]
    return jsonify(check_new_releases(series_name, owned))


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
    media = db.get_or_404(Media, media_id)
    result = estimate_value_lastdodo(media.title, media.series)
    if result.get("value"):
        media.estimated_value = result["value"]
        media.value_source = "lastdodo"
        db.session.commit()
    return jsonify(result)
