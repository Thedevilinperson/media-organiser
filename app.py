import os
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler

from models import (
    db, MediaType, Owner, Media, Loan, Setting,
    get_setting, set_setting, seed_defaults, CONDITIONS,
)
from series_analysis import missing_numbers_per_series, check_new_releases
from lookups import lookup_barcode, analyze_cover_ocr, analyze_cover_ai, estimate_value_lastdodo
from ha_integration import push_ha_notification
from importer import read_import_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(DATA_DIR, 'mediabeheer.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-verander-mij")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB uploads

db.init_app(app)

STRIP_PROFILES = ("strip",)  # profielen die als "reeks met nummer" gelden voor analyse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def current_media_types():
    return MediaType.query.order_by(MediaType.label).all()


def current_owners():
    return Owner.query.order_by(Owner.name).all()


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"jpg", "jpeg", "png", "webp"}


# ---------------------------------------------------------------------------
# Basisweergave
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    type_filter = request.args.get("type", "")
    owner_filter = request.args.get("owner", "")
    series_filter = request.args.get("series", "")
    title_filter = request.args.get("title", "")

    query = Media.query

    if type_filter:
        query = query.join(MediaType).filter(MediaType.code == type_filter)
    if owner_filter:
        query = query.join(Owner, isouter=True).filter(Owner.name == owner_filter)
    if series_filter:
        query = query.filter(Media.series == series_filter)
    if title_filter:
        query = query.filter(Media.title == title_filter)

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Media.title.ilike(like),
                Media.series.ilike(like),
                Media.author.ilike(like),
                Media.comment.ilike(like),
                Media.musician.ilike(like),
                Media.collection.ilike(like),
                Media.barcode.ilike(like),
            )
        )

    items = query.all()

    # Sortering: strips/comics/manga/anime alfabetisch op reeks, dan op nummer.
    # Andere types op titel.
    def sort_key(m):
        if m.media_type and m.media_type.field_profile == "strip":
            return (0, (m.series or "").lower(), m.series_number if m.series_number is not None else 0)
        return (1, (m.title or "").lower(), 0)

    items = sorted(items, key=sort_key)

    # Totalen per type (op de VOLLEDIGE ongefilterde set, zoals gevraagd: "totale
    # aantal per type media" bovenaan de basisweergave)
    totals = (
        db.session.query(MediaType.label, db.func.count(Media.id))
        .join(Media, Media.media_type_id == MediaType.id, isouter=True)
        .group_by(MediaType.id)
        .order_by(MediaType.label)
        .all()
    )

    # Cascaderende filteropties: elke lijst wordt beperkt door de reeds
    # gekozen andere filters (zonder de eigen filter, zodat je hem nog kan
    # wijzigen), plus de zoekterm.
    def options_for(exclude):
        base = Media.query.join(MediaType).join(Owner, isouter=True)
        if type_filter and exclude != "type":
            base = base.filter(MediaType.code == type_filter)
        if owner_filter and exclude != "owner":
            base = base.filter(Owner.name == owner_filter)
        if series_filter and exclude != "series":
            base = base.filter(Media.series == series_filter)
        if title_filter and exclude != "title":
            base = base.filter(Media.title == title_filter)
        if q:
            like = f"%{q}%"
            base = base.filter(
                db.or_(
                    Media.title.ilike(like), Media.series.ilike(like),
                    Media.author.ilike(like), Media.comment.ilike(like),
                )
            )
        return base

    type_options = sorted({m.media_type.label for m in options_for("type") if m.media_type})
    owner_options = sorted({m.owner.name for m in options_for("owner") if m.owner})
    series_options = sorted({m.series for m in options_for("series") if m.series})
    title_options = sorted({m.title for m in options_for("title") if m.title})

    return render_template(
        "index.html",
        items=items,
        totals=totals,
        q=q,
        type_filter=type_filter,
        owner_filter=owner_filter,
        series_filter=series_filter,
        title_filter=title_filter,
        type_options=type_options,
        owner_options=owner_options,
        series_options=series_options,
        title_options=title_options,
    )


# ---------------------------------------------------------------------------
# Ingave: manueel
# ---------------------------------------------------------------------------
@app.route("/media/add", methods=["GET", "POST"])
def add_media():
    prefill = {}
    if request.method == "GET":
        # vanuit barcode-/foto-herkenning kunnen velden meegegeven worden via querystring
        prefill = request.args.to_dict()

    if request.method == "POST":
        media = Media()
        _apply_form_to_media(media, request.form)

        cover = request.files.get("cover_image")
        if cover and cover.filename and allowed_image(cover.filename):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{cover.filename}")
            cover.save(os.path.join(UPLOAD_DIR, filename))
            media.cover_image = filename

        db.session.add(media)
        db.session.commit()
        flash("Media toegevoegd.", "success")
        return redirect(url_for("index"))

    return render_template(
        "media_form.html",
        media=None,
        prefill=prefill,
        media_types=current_media_types(),
        owners=current_owners(),
        conditions=CONDITIONS,
    )


@app.route("/media/<int:media_id>/edit", methods=["GET", "POST"])
def edit_media(media_id):
    media = Media.query.get_or_404(media_id)
    if request.method == "POST":
        _apply_form_to_media(media, request.form)
        cover = request.files.get("cover_image")
        if cover and cover.filename and allowed_image(cover.filename):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{cover.filename}")
            cover.save(os.path.join(UPLOAD_DIR, filename))
            media.cover_image = filename
        db.session.commit()
        flash("Media bijgewerkt.", "success")
        return redirect(url_for("index"))

    return render_template(
        "media_form.html",
        media=media,
        prefill={},
        media_types=current_media_types(),
        owners=current_owners(),
        conditions=CONDITIONS,
    )


@app.route("/media/<int:media_id>/delete", methods=["POST"])
def delete_media(media_id):
    media = Media.query.get_or_404(media_id)
    db.session.delete(media)
    db.session.commit()
    flash("Media verwijderd.", "info")
    return redirect(url_for("index"))


def _apply_form_to_media(media, form):
    type_code = form.get("media_type")
    mt = MediaType.query.filter_by(code=type_code).first()
    if mt:
        media.media_type_id = mt.id

    owner_id = form.get("owner_id")
    media.owner_id = int(owner_id) if owner_id else None

    media.title = form.get("title", "").strip()
    media.series = form.get("series", "").strip() or None
    series_number = form.get("series_number", "").strip()
    media.series_number = float(series_number) if series_number else None
    media.comment = form.get("comment", "").strip() or None
    media.barcode = form.get("barcode", "").strip() or None

    media.author = form.get("author", "").strip() or None
    media.collection = form.get("collection", "").strip() or None
    coll_num = form.get("collection_number", "").strip()
    media.collection_number = int(coll_num) if coll_num.isdigit() else None
    print_num = form.get("print_number", "").strip()
    media.print_number = int(print_num) if print_num.isdigit() else None
    media.is_duplicate = form.get("is_duplicate") == "on"
    media.is_hardcover = form.get("is_hardcover") == "on"
    media.condition = form.get("condition") or None

    media.musician = form.get("musician", "").strip() or None
    # "year" (CD) en "year_dvd" (DVD) zijn twee formuliervelden voor hetzelfde
    # onderliggende jaar-veld; de JS in media_form.html kopieert year_dvd naar
    # year vóór het versturen, maar we vangen het hier ook server-side op
    # zodat het robuust blijft (bv. bij JS uitgeschakeld, of massa-import).
    year = form.get("year", "").strip() or form.get("year_dvd", "").strip()
    media.year = int(year) if year.isdigit() else None

    media.audio_language = form.get("audio_language", "").strip() or None
    media.subtitle_language = form.get("subtitle_language", "").strip() or None

    value = form.get("estimated_value", "").strip()
    media.estimated_value = float(value.replace(",", ".")) if value else None


# ---------------------------------------------------------------------------
# Ingave: barcode scannen
# ---------------------------------------------------------------------------
@app.route("/media/add/scan")
def scan_barcode():
    return render_template("scan.html")


@app.route("/api/lookup/barcode/<code>")
def api_lookup_barcode(code):
    return jsonify(lookup_barcode(code))


# ---------------------------------------------------------------------------
# Ingave: foto analyseren
# ---------------------------------------------------------------------------
@app.route("/media/add/photo", methods=["GET", "POST"])
def add_by_photo():
    if request.method == "GET":
        return render_template("photo_add.html")

    photo = request.files.get("photo")
    if not photo or not photo.filename:
        flash("Geen foto ontvangen.", "error")
        return redirect(url_for("add_by_photo"))

    filename = secure_filename(f"{datetime.utcnow().timestamp()}_{photo.filename}")
    path = os.path.join(UPLOAD_DIR, filename)
    photo.save(path)

    api_key = get_setting("ai_api_key")
    if api_key:
        result = analyze_cover_ai(path, api_key)
        method = "ai"
    else:
        result = analyze_cover_ocr(path)
        method = "ocr"

    fields = result.get("fields", {})
    fields["cover_image_existing"] = filename
    return render_template(
        "photo_add.html",
        result=result,
        fields=fields,
        method=method,
        media_types=current_media_types(),
        owners=current_owners(),
    )


# ---------------------------------------------------------------------------
# Reeksanalyse
# ---------------------------------------------------------------------------
@app.route("/analysis/series")
def analysis_series():
    items = Media.query.join(MediaType).filter(MediaType.field_profile.in_(STRIP_PROFILES)).all()
    # ook boeken met een reeks meenemen
    items += Media.query.join(MediaType).filter(MediaType.field_profile == "boek", Media.series.isnot(None)).all()

    analysis = missing_numbers_per_series(items)
    return render_template("series_analysis.html", analysis=analysis)


@app.route("/analysis/series/check-new", methods=["POST"])
def analysis_series_check_new():
    series = request.form.get("series")
    owned = [float(n) for n in request.form.getlist("owned")]
    result = check_new_releases(series, owned)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Waarde van de collectie
# ---------------------------------------------------------------------------
@app.route("/analysis/value")
def analysis_value():
    items = Media.query.all()
    per_type = {}
    for m in items:
        label = m.media_type.label if m.media_type else "Onbekend"
        per_type.setdefault(label, {"count": 0, "known_value": 0.0, "known_count": 0})
        per_type[label]["count"] += 1
        if m.estimated_value:
            per_type[label]["known_value"] += m.estimated_value
            per_type[label]["known_count"] += 1

    total_value = sum(v["known_value"] for v in per_type.values())
    return render_template("value.html", per_type=per_type, total_value=total_value, items=items)


@app.route("/analysis/value/estimate/<int:media_id>", methods=["POST"])
def analysis_value_estimate(media_id):
    media = Media.query.get_or_404(media_id)
    result = estimate_value_lastdodo(media.title, media.series)
    if result.get("value"):
        media.estimated_value = result["value"]
        db.session.commit()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Uitleenmodule
# ---------------------------------------------------------------------------
@app.route("/lending")
def lending():
    active_loans = Loan.query.filter_by(returned_date=None).order_by(Loan.loan_date).all()
    history = Loan.query.filter(Loan.returned_date.isnot(None)).order_by(Loan.returned_date.desc()).limit(50).all()
    today = date.today()
    for loan in active_loans:
        loan.is_overdue = (today - loan.loan_date) > timedelta(days=30)
    available_media = Media.query.order_by(Media.title).all()
    return render_template(
        "lending.html", active_loans=active_loans, history=history,
        available_media=available_media, today=today.isoformat(),
    )


@app.route("/lending/add", methods=["POST"])
def lending_add():
    media_id = int(request.form["media_id"])
    borrower = request.form.get("borrower_name", "").strip()
    loan_date_str = request.form.get("loan_date") or date.today().isoformat()
    if not borrower:
        flash("Naam van de ontlener is verplicht.", "error")
        return redirect(url_for("lending"))
    loan = Loan(media_id=media_id, borrower_name=borrower, loan_date=date.fromisoformat(loan_date_str))
    db.session.add(loan)
    db.session.commit()
    flash("Uitlening geregistreerd.", "success")
    return redirect(url_for("lending"))


@app.route("/lending/<int:loan_id>/return", methods=["POST"])
def lending_return(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    loan.returned_date = date.today()
    db.session.commit()
    flash("Item als teruggebracht gemarkeerd.", "success")
    return redirect(url_for("lending"))


def check_overdue_loans_job():
    """Achtergrondtaak: pusht een HA-melding voor uitleningen > 1 maand oud."""
    with app.app_context():
        ha_url = get_setting("ha_url")
        ha_token = get_setting("ha_token")
        if not ha_url or not ha_token:
            return
        cutoff = date.today() - timedelta(days=30)
        overdue = Loan.query.filter(Loan.returned_date.is_(None), Loan.loan_date <= cutoff, Loan.notified_overdue.is_(False)).all()
        for loan in overdue:
            media = Media.query.get(loan.media_id)
            title = media.title if media else "onbekende titel"
            ok, err = push_ha_notification(
                ha_url, ha_token,
                title="Media te lang uitgeleend",
                message=f"'{title}' is sinds {loan.loan_date} uitgeleend aan {loan.borrower_name} (meer dan 1 maand geleden).",
            )
            if ok:
                loan.notified_overdue = True
        db.session.commit()


# ---------------------------------------------------------------------------
# Instellingen
# ---------------------------------------------------------------------------
@app.route("/settings", methods=["GET"])
def settings():
    return render_template(
        "settings.html",
        owners=current_owners(),
        media_types=current_media_types(),
        ai_api_key=get_setting("ai_api_key", ""),
        ha_url=get_setting("ha_url", ""),
        ha_token=get_setting("ha_token", ""),
    )


@app.route("/settings/owner/add", methods=["POST"])
def settings_owner_add():
    name = request.form.get("name", "").strip()
    if name and not Owner.query.filter_by(name=name).first():
        db.session.add(Owner(name=name))
        db.session.commit()
        flash(f"Eigenaar '{name}' toegevoegd.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/owner/<int:owner_id>/delete", methods=["POST"])
def settings_owner_delete(owner_id):
    owner = Owner.query.get_or_404(owner_id)
    db.session.delete(owner)
    db.session.commit()
    flash("Eigenaar verwijderd.", "info")
    return redirect(url_for("settings"))


@app.route("/settings/mediatype/add", methods=["POST"])
def settings_mediatype_add():
    code = request.form.get("code", "").strip().lower()
    label = request.form.get("label", "").strip()
    profile = request.form.get("field_profile", "vrij")
    if code and label and not MediaType.query.filter_by(code=code).first():
        db.session.add(MediaType(code=code, label=label, field_profile=profile))
        db.session.commit()
        flash(f"Mediatype '{label}' toegevoegd.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/mediatype/<int:type_id>/delete", methods=["POST"])
def settings_mediatype_delete(type_id):
    mt = MediaType.query.get_or_404(type_id)
    db.session.delete(mt)
    db.session.commit()
    flash("Mediatype verwijderd.", "info")
    return redirect(url_for("settings"))


@app.route("/settings/save", methods=["POST"])
def settings_save():
    set_setting("ai_api_key", request.form.get("ai_api_key", "").strip())
    set_setting("ha_url", request.form.get("ha_url", "").strip())
    set_setting("ha_token", request.form.get("ha_token", "").strip())
    flash("Instellingen opgeslagen.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/import", methods=["POST"])
def settings_import():
    file = request.files.get("import_file")
    if not file or not file.filename.endswith(".xlsx"):
        flash("Kies een geldig .xlsx-bestand.", "error")
        return redirect(url_for("settings"))

    tmp_path = os.path.join(UPLOAD_DIR, secure_filename(file.filename))
    file.save(tmp_path)

    records = read_import_file(tmp_path)
    created = 0
    for rec in records:
        type_code = str(rec.get("media_type_code", "")).strip().lower()
        mt = MediaType.query.filter_by(code=type_code).first()
        if not mt:
            continue  # onbekend type: rij overslaan (zichtbaar in resultaatmelding)

        owner = None
        owner_name = rec.get("owner_name")
        if owner_name:
            owner = Owner.query.filter_by(name=owner_name).first()
            if not owner:
                owner = Owner(name=owner_name)
                db.session.add(owner)
                db.session.flush()

        media = Media(
            media_type_id=mt.id,
            owner_id=owner.id if owner else None,
            title=str(rec.get("title", "")),
            series=rec.get("series"),
            series_number=rec.get("series_number"),
            author=rec.get("author"),
            collection=rec.get("collection"),
            collection_number=rec.get("collection_number"),
            print_number=rec.get("print_number"),
            is_duplicate=bool(rec.get("is_duplicate", False)),
            is_hardcover=bool(rec.get("is_hardcover", False)),
            condition=rec.get("condition"),
            comment=rec.get("comment"),
            musician=rec.get("musician"),
            year=rec.get("year"),
            audio_language=rec.get("audio_language"),
            subtitle_language=rec.get("subtitle_language"),
            barcode=str(rec.get("barcode")) if rec.get("barcode") else None,
            estimated_value=rec.get("estimated_value"),
        )
        db.session.add(media)
        created += 1

    db.session.commit()
    flash(f"{created} van {len(records)} rijen geïmporteerd.", "success")
    return redirect(url_for("settings"))


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    seed_defaults()

scheduler = BackgroundScheduler()
scheduler.add_job(check_overdue_loans_job, "interval", hours=24, id="overdue_check")
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8099))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
