"""Ingave en beheer van media: manueel, via barcode en via foto."""
import os

from flask import (
    Blueprint, current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)

from extensions import db
from models import CONDITIONS, CustomField, FIELD_LABELS, Media, MediaType, Owner, get_setting
from security import allowed_image, clean_text, safe_float, safe_int, unique_filename
from services.images import save_cover
from services.lookups import ALLOWED_LOOKUP_FIELDS, analyze_cover_ai, analyze_cover_ocr, lookup_barcode

media_bp = Blueprint("media", __name__, url_prefix="/media")


def _form_context(media=None, prefill=None):
    media_types = db.session.query(MediaType).order_by(MediaType.label).all()
    custom_fields = db.session.query(CustomField).order_by(CustomField.label).all()

    # Wat het formulier per type moet tonen en wat verplicht is. De browser
    # gebruikt dit om bij het wisselen van type meteen de juiste velden te
    # tonen; de server controleert het bij het opslaan nog eens.
    config = {}
    for media_type in media_types:
        settings = media_type.field_settings()
        config[media_type.code] = {
            "fields": {key: {"visible": item["visible"], "required": item["required"]}
                       for key, item in settings.items()},
            "custom": {
                f"cf_{f.key}": {"visible": f.media_type_id in (None, media_type.id),
                                "required": bool(f.required)}
                for f in custom_fields
            },
        }

    selected = None
    if media is not None and media.media_type:
        selected = media.media_type
    elif prefill and prefill.get("media_type"):
        selected = next((t for t in media_types if t.code == prefill["media_type"]), None)
    if selected is None and media_types:
        selected = media_types[0]

    return {
        "media": media,
        "prefill": prefill or {},
        "media_types": media_types,
        "owners": db.session.query(Owner).order_by(Owner.name).all(),
        "conditions": CONDITIONS,
        "custom_fields": custom_fields,
        "field_config": config,
        "current": selected.field_settings() if selected else {},
        "current_type": selected,
    }


def _apply_form(media, form):
    """
    Zet de formuliergegevens op het model. Alleen velden die voor dit
    mediatype zichtbaar zijn worden overgenomen, en verplichte velden worden
    hier nog eens gecontroleerd: de browser kan die controle overslaan, de
    server niet.
    """
    media_type = db.session.query(MediaType).filter_by(code=form.get("media_type", "")).first()
    if media_type is None:
        return "Kies een geldig mediatype."
    media.media_type_id = media_type.id

    title = clean_text(form.get("title"), 300, allow_empty_none=False)
    if not title:
        return "Een titel is verplicht."
    media.title = title

    zichtbaar = media_type.visible_fields()
    verplicht = media_type.required_fields()

    owner_id = safe_int(form.get("owner_id"))
    waarden = {
        "owner_id": owner_id if owner_id and db.session.get(Owner, owner_id) else None,
        "series": clean_text(form.get("series"), 300),
        "series_number": safe_float(form.get("series_number"), None, minimum=0, maximum=10000),
        "author": clean_text(form.get("author"), 200),
        "musician": clean_text(form.get("musician"), 200),
        "collection": clean_text(form.get("collection"), 200),
        "collection_number": safe_int(form.get("collection_number"), None, 0, 100000),
        "print_number": safe_int(form.get("print_number"), None, 0, 1000),
        "is_hardcover": form.get("is_hardcover") == "on",
        "is_duplicate": form.get("is_duplicate") == "on",
        "condition": form.get("condition") if form.get("condition") in CONDITIONS else None,
        "year": safe_int(form.get("year"), None, 0, 2200),
        "audio_language": clean_text(form.get("audio_language"), 100),
        "subtitle_language": clean_text(form.get("subtitle_language"), 100),
        "barcode": clean_text(form.get("barcode"), 64),
        "estimated_value": safe_float(form.get("estimated_value"), None, 0, 1000000),
        "comment": clean_text(form.get("comment"), 4000),
    }

    for key in verplicht:
        if key in ("cover_image",):
            continue
        waarde = waarden.get(key)
        if waarde in (None, "", False):
            return f"Het veld '{FIELD_LABELS.get(key, key)}' is verplicht voor {media_type.label}."

    for key, waarde in waarden.items():
        if key in zichtbaar:
            setattr(media, key, waarde)

    # Bij een cd is het muzikantveld de maker; blijft het leeg, dan valt het
    # terug op de auteur.
    if media_type.field_profile == "cd" and not media.musician:
        media.musician = media.author

    if "estimated_value" in zichtbaar:
        media.value_source = "manueel" if media.estimated_value is not None else None

    # Eigen velden uit Instellingen.
    values = dict(media.custom_fields or {})
    for field in db.session.query(CustomField).all():
        if field.media_type_id not in (None, media.media_type_id):
            continue
        raw = form.get(f"cf_{field.key}")
        if field.field_type == "checkbox":
            waarde = raw == "on"
        elif field.field_type == "number":
            waarde = safe_float(raw)
        else:
            waarde = clean_text(raw, 500)
        if field.required and waarde in (None, "", False):
            return f"Het veld '{field.label}' is verplicht voor {media_type.label}."
        values[field.key] = waarde
    media.custom_fields = {k: v for k, v in values.items() if v not in (None, "")}
    return None


def _handle_cover(media):
    """
    Neemt een nieuw geuploade kaftfoto over, of hergebruikt de foto die bij
    de foto-analyse al bewaard werd. Die naam wordt streng gecontroleerd,
    zodat er via het formulier geen willekeurig pad ingesmokkeld kan worden.
    """
    existing = request.form.get("cover_image", "")
    if existing and COVER_NAME_RE.match(existing):
        if os.path.exists(os.path.join(current_app.config["UPLOAD_DIR"], existing)):
            media.cover_image = existing

    cover = request.files.get("cover_image_file")
    if not cover or not cover.filename:
        return
    if not allowed_image(cover.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
        flash("Kaftfoto geweigerd: enkel jpg, png of webp.", "error")
        return
    name, path = unique_filename(cover.filename, current_app.config["UPLOAD_DIR"])
    ok, error = save_cover(cover, path, current_app.config["COVER_MAX_PIXELS"])
    if ok:
        media.cover_image = name
    else:
        try:
            os.remove(path)
        except OSError:
            pass
        flash(f"Kaftfoto geweigerd: {error}", "error")


# ---------------------------------------------------------------------------
# Manueel toevoegen en wijzigen
# ---------------------------------------------------------------------------
@media_bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        media = Media()
        error = _apply_form(media, request.form)
        if error:
            flash(error, "error")
            return render_template("media_form.html", **_form_context(prefill=request.form))
        _handle_cover(media)
        db.session.add(media)
        db.session.commit()
        flash(f"'{media.title}' toegevoegd.", "success")
        return redirect(url_for("main.index"))

    # Vanuit barcode of foto komen velden mee via de querystring; enkel
    # bekende velden worden overgenomen.
    prefill = {k: v for k, v in request.args.items() if k in ALLOWED_LOOKUP_FIELDS | {"media_type", "cover_image"}}
    return render_template("media_form.html", **_form_context(prefill=prefill))


@media_bp.route("/<int:media_id>/edit", methods=["GET", "POST"])
def edit(media_id):
    media = db.get_or_404(Media, media_id)
    if request.method == "POST":
        error = _apply_form(media, request.form)
        if error:
            flash(error, "error")
            return render_template("media_form.html", **_form_context(media=media))
        _handle_cover(media)
        db.session.commit()
        flash("Wijzigingen opgeslagen.", "success")
        return redirect(url_for("main.index"))
    return render_template("media_form.html", **_form_context(media=media))


@media_bp.route("/<int:media_id>/delete", methods=["POST"])
def delete(media_id):
    media = db.get_or_404(Media, media_id)
    if media.cover_image:
        try:
            os.remove(os.path.join(current_app.config["UPLOAD_DIR"], media.cover_image))
        except OSError:
            pass
    db.session.delete(media)
    db.session.commit()
    flash("Item verwijderd.", "info")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Ingave via barcode
# ---------------------------------------------------------------------------
@media_bp.route("/scan")
def scan():
    return render_template("scan.html")


@media_bp.route("/api/barcode/<code>")
def api_barcode(code):
    return jsonify(lookup_barcode(code[:40]))


# ---------------------------------------------------------------------------
# Ingave via foto
# ---------------------------------------------------------------------------
@media_bp.route("/photo", methods=["GET", "POST"])
def photo():
    if request.method == "GET":
        return render_template("photo_add.html")

    photo_file = request.files.get("photo")
    if not photo_file or not photo_file.filename:
        flash("Geen foto ontvangen.", "error")
        return redirect(url_for("media.photo"))
    if not allowed_image(photo_file.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
        flash("Enkel jpg, png of webp.", "error")
        return redirect(url_for("media.photo"))

    name, path = unique_filename(photo_file.filename, current_app.config["UPLOAD_DIR"])
    ok, error = save_cover(photo_file, path, current_app.config["COVER_MAX_PIXELS"])
    if not ok:
        try:
            os.remove(path)
        except OSError:
            pass
        flash(f"Foto geweigerd: {error}", "error")
        return redirect(url_for("media.photo"))

    api_key = get_setting("ai_api_key")
    if api_key:
        result = analyze_cover_ai(path, api_key, base_url=get_setting("ai_endpoint") or None)
        method = "ai"
    else:
        result = analyze_cover_ocr(path)
        method = "ocr"

    fields = dict(result.get("fields") or {})
    fields["cover_image"] = name
    return render_template("photo_add.html", result=result, fields=fields, method=method)
