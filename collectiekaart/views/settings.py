"""Instellingen: eigenaars, mediatypes, eigen velden, koppelingen en import."""
import os

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from extensions import db
from models import CONDITIONS, CustomField, FIELD_PROFILES, Media, MediaType, Owner, get_setting, set_setting
from security import clean_text, safe_float, safe_int, valid_key
from services.ha_integration import test_connection
from services.importer import read_import_file

settings_bp = Blueprint("settings", __name__, url_prefix="/instellingen")


@settings_bp.route("/")
def index():
    ha_token = get_setting("ha_token", "")
    ai_key = get_setting("ai_api_key", "")
    return render_template(
        "settings.html",
        owners=db.session.query(Owner).order_by(Owner.name).all(),
        media_types=db.session.query(MediaType).order_by(MediaType.label).all(),
        custom_fields=db.session.query(CustomField).order_by(CustomField.label).all(),
        field_profiles=FIELD_PROFILES,
        ai_endpoint=get_setting("ai_endpoint", ""),
        ha_url=get_setting("ha_url", ""),
        # Geheimen worden nooit teruggestuurd naar de browser; enkel of ze
        # ingevuld zijn (zie SECURITY.md, bevinding B2).
        has_ai_key=bool(ai_key),
        has_ha_token=bool(ha_token),
    )


# ---------------------------------------------------------------------------
# Eigenaars
# ---------------------------------------------------------------------------
@settings_bp.route("/eigenaar/add", methods=["POST"])
def owner_add():
    name = clean_text(request.form.get("name"), 100)
    if name and not db.session.query(Owner).filter_by(name=name).first():
        db.session.add(Owner(name=name))
        db.session.commit()
        flash(f"Eigenaar '{name}' toegevoegd.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/eigenaar/<int:owner_id>/delete", methods=["POST"])
def owner_delete(owner_id):
    owner = db.get_or_404(Owner, owner_id)
    in_use = db.session.query(Media).filter_by(owner_id=owner.id).count()
    if in_use:
        flash(f"'{owner.name}' staat nog bij {in_use} item(s) en werd niet verwijderd.", "error")
    else:
        db.session.delete(owner)
        db.session.commit()
        flash("Eigenaar verwijderd.", "info")
    return redirect(url_for("settings.index"))


# ---------------------------------------------------------------------------
# Mediatypes
# ---------------------------------------------------------------------------
@settings_bp.route("/mediatype/add", methods=["POST"])
def mediatype_add():
    code = (request.form.get("code") or "").strip().lower()
    label = clean_text(request.form.get("label"), 100)
    profile = request.form.get("field_profile", "vrij")

    if not valid_key(code):
        flash("De code mag enkel kleine letters, cijfers en liggende streepjes bevatten.", "error")
    elif not label:
        flash("Een weergavenaam is verplicht.", "error")
    elif profile not in FIELD_PROFILES:
        flash("Onbekend veldenprofiel.", "error")
    elif db.session.query(MediaType).filter_by(code=code).first():
        flash("Die code bestaat al.", "error")
    else:
        db.session.add(MediaType(code=code, label=label, field_profile=profile))
        db.session.commit()
        flash(f"Mediatype '{label}' toegevoegd.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/mediatype/<int:type_id>/delete", methods=["POST"])
def mediatype_delete(type_id):
    media_type = db.get_or_404(MediaType, type_id)
    in_use = db.session.query(Media).filter_by(media_type_id=media_type.id).count()
    if in_use:
        flash(f"'{media_type.label}' bevat nog {in_use} item(s) en werd niet verwijderd.", "error")
    else:
        db.session.delete(media_type)
        db.session.commit()
        flash("Mediatype verwijderd.", "info")
    return redirect(url_for("settings.index"))


# ---------------------------------------------------------------------------
# Eigen velden (vereiste 1.f.iv)
# ---------------------------------------------------------------------------
@settings_bp.route("/veld/add", methods=["POST"])
def field_add():
    key = (request.form.get("key") or "").strip().lower().replace(" ", "_")
    label = clean_text(request.form.get("label"), 100)
    field_type = request.form.get("field_type", "text")
    type_id = safe_int(request.form.get("media_type_id"))

    if not valid_key(key):
        flash("De interne naam mag enkel kleine letters, cijfers en liggende streepjes bevatten.", "error")
    elif not label:
        flash("Een weergavenaam is verplicht.", "error")
    elif field_type not in ("text", "number", "checkbox"):
        flash("Onbekend veldtype.", "error")
    elif db.session.query(CustomField).filter_by(key=key, media_type_id=type_id).first():
        flash("Dat veld bestaat al voor dit type.", "error")
    else:
        db.session.add(CustomField(key=key, label=label, field_type=field_type, media_type_id=type_id))
        db.session.commit()
        flash(f"Veld '{label}' toegevoegd.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/veld/<int:field_id>/delete", methods=["POST"])
def field_delete(field_id):
    field = db.get_or_404(CustomField, field_id)
    db.session.delete(field)
    db.session.commit()
    flash("Veld verwijderd. Reeds ingevulde waarden blijven bewaard.", "info")
    return redirect(url_for("settings.index"))


# ---------------------------------------------------------------------------
# Koppelingen
# ---------------------------------------------------------------------------
@settings_bp.route("/opslaan", methods=["POST"])
def save():
    # Een leeg veld betekent 'niet wijzigen'; wissen doe je met de knop.
    ai_key = (request.form.get("ai_api_key") or "").strip()
    if ai_key:
        set_setting("ai_api_key", ai_key)
    if request.form.get("clear_ai_key") == "on":
        set_setting("ai_api_key", "")

    ha_token = (request.form.get("ha_token") or "").strip()
    if ha_token:
        set_setting("ha_token", ha_token)
    if request.form.get("clear_ha_token") == "on":
        set_setting("ha_token", "")

    set_setting("ai_endpoint", clean_text(request.form.get("ai_endpoint"), 300) or "")
    set_setting("ha_url", clean_text(request.form.get("ha_url"), 300) or "")

    flash("Instellingen opgeslagen.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/ha/test", methods=["POST"])
def ha_test():
    ok, message = test_connection(get_setting("ha_url"), get_setting("ha_token"))
    return jsonify({"ok": ok, "message": message})


# ---------------------------------------------------------------------------
# Massa-import
# ---------------------------------------------------------------------------
@settings_bp.route("/import", methods=["POST"])
def do_import():
    upload = request.files.get("import_file")
    if not upload or not upload.filename.lower().endswith(".xlsx"):
        flash("Kies een geldig .xlsx-bestand.", "error")
        return redirect(url_for("settings.index"))

    tmp_path = os.path.join(
        current_app.config["DATA_DIR"], "import_" + secure_filename(upload.filename)
    )
    upload.save(tmp_path)

    try:
        records = read_import_file(tmp_path)
    except Exception as exc:
        flash(f"Kon het bestand niet lezen: {exc}", "error")
        return redirect(url_for("settings.index"))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    types = {t.code: t for t in db.session.query(MediaType).all()}
    owners = {o.name: o for o in db.session.query(Owner).all()}

    created, skipped = 0, []
    for line, record in enumerate(records, start=2):
        code = str(record.get("media_type_code", "")).strip().lower()
        media_type = types.get(code)
        if not media_type:
            skipped.append(f"rij {line}: onbekend type '{code}'")
            continue

        title = str(record.get("title", "")).strip()
        if not title:
            skipped.append(f"rij {line}: geen titel")
            continue

        owner = None
        owner_name = str(record.get("owner_name", "")).strip()
        if owner_name:
            owner = owners.get(owner_name)
            if not owner:
                owner = Owner(name=owner_name[:100])
                db.session.add(owner)
                db.session.flush()
                owners[owner_name] = owner

        condition = str(record.get("condition", "")).strip().lower()
        db.session.add(Media(
            media_type_id=media_type.id,
            owner_id=owner.id if owner else None,
            title=title[:300],
            series=clean_text(record.get("series"), 300),
            series_number=safe_float(record.get("series_number")),
            author=clean_text(record.get("author"), 200),
            collection=clean_text(record.get("collection"), 200),
            collection_number=safe_int(record.get("collection_number")),
            print_number=safe_int(record.get("print_number")),
            is_duplicate=bool(record.get("is_duplicate", False)),
            is_hardcover=bool(record.get("is_hardcover", False)),
            condition=condition if condition in CONDITIONS else None,
            comment=clean_text(record.get("comment"), 4000),
            musician=clean_text(record.get("musician"), 200),
            year=safe_int(record.get("year"), None, 0, 2200),
            audio_language=clean_text(record.get("audio_language"), 100),
            subtitle_language=clean_text(record.get("subtitle_language"), 100),
            barcode=clean_text(str(record.get("barcode") or ""), 64),
            estimated_value=safe_float(record.get("estimated_value"), None, 0, 1000000),
            value_source="manueel" if record.get("estimated_value") else None,
        ))
        created += 1

    db.session.commit()
    flash(f"{created} van {len(records)} rijen geïmporteerd.", "success")
    if skipped:
        flash("Overgeslagen: " + "; ".join(skipped[:10]) + ("…" if len(skipped) > 10 else ""), "info")
    return redirect(url_for("settings.index"))
