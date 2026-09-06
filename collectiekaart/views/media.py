"""Ingave en beheer van media: manueel, via barcode, via foto en via een kopie."""
import os
import re

from flask import (
    Blueprint, current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)
from sqlalchemy import func

from extensions import db
from models import CONDITIONS, CustomField, FIELD_LABELS, Media, MediaType, Owner, get_setting
from security import allowed_image, clean_text, safe_float, safe_int, unique_filename
from services.images import save_cover
from services.lookups import (
    ALLOWED_LOOKUP_FIELDS, analyze_cover_ai, analyze_cover_ocr, lookup_barcode_detailed,
)

media_bp = Blueprint("media", __name__, url_prefix="/media")

# Bestandsnamen van kaftfoto's worden door unique_filename() opgebouwd uit een
# willekeurig token plus een gecontroleerde extensie. Wat via het formulier
# terugkomt, moet exact dat patroon volgen; anders zou er een willekeurig pad
# ingesmokkeld kunnen worden (zie SECURITY.md, bevinding B4).
COVER_NAME_RE = re.compile(r"^[0-9a-f]{24}\.(jpg|jpeg|png|webp)$", re.I)

# Velden die overgenomen worden als je een nieuw item op een bestaand item
# baseert. Barcode, kaftfoto, waarde en commentaar horen bij dát ene exemplaar
# en worden bewust niet meegekopieerd.
COPY_FIELDS = (
    "owner_id", "series", "series_number", "author", "musician",
    "collection", "collection_number", "print_number", "condition",
    "year", "audio_language", "subtitle_language",
    "is_hardcover", "is_duplicate",
)

# Alles wat op het formulier ingevuld kan worden, met het soort waarde. Wordt
# gebruikt om één set beginwaarden op te bouwen, of die nu van een bestaand
# item komt, van een barcode, van een foto of van een kopie.
FORM_FIELDS = {
    "title": "text",
    "owner_id": "int",
    "series": "text",
    "series_number": "number",
    "author": "text",
    "musician": "text",
    "collection": "text",
    "collection_number": "int",
    "print_number": "int",
    "year": "int",
    "condition": "text",
    "audio_language": "text",
    "subtitle_language": "text",
    "barcode": "text",
    "estimated_value": "number",
    "comment": "text",
    "is_hardcover": "bool",
    "is_duplicate": "bool",
}


def _leeg(waarde):
    """
    Of een waarde als 'niet ingevuld' geldt. Bewust niet met `in (None, "",
    False)`: in Python is 0 == False, waardoor een geschatte waarde van 0 of
    een reeksnummer 0 anders ten onrechte als leeg gold.
    """
    if waarde is None:
        return True
    if isinstance(waarde, bool):
        return waarde is False
    if isinstance(waarde, str):
        return waarde.strip() == ""
    return False


def _as_text(value, soort):
    """Zet een waarde om naar wat er in een invoerveld hoort te staan."""
    if value is None or value == "":
        return "" if soort != "bool" else False
    if soort == "bool":
        return value is True or str(value).lower() in ("1", "true", "on", "ja", "yes")
    if soort == "number":
        number = safe_float(value)
        if number is None:
            return ""
        return str(int(number)) if float(number).is_integer() else str(number)
    if soort == "int":
        number = safe_int(value)
        return "" if number is None else str(number)
    return str(value)


def _field_values(media, prefill, custom_fields):
    """
    Eén set beginwaarden voor het formulier.

    Vroeger las het sjabloon voor sommige velden uit het item en voor andere
    uit de querystring, waardoor een deel van de gegevens bij het toevoegen
    verloren ging. Nu wordt alles hier samengevoegd: een bestaand item wint,
    en anders geldt wat er als voorinvulling meekwam.
    """
    values = {}
    for key, soort in FORM_FIELDS.items():
        waarde = getattr(media, key, None) if media is not None else None
        if _leeg(waarde):
            waarde = prefill.get(key) if prefill else None
        values[key] = _as_text(waarde, soort)

    eigen = dict((media.custom_fields or {}) if media is not None else {})
    for field in custom_fields:
        sleutel = f"cf_{field.key}"
        waarde = eigen.get(field.key)
        if _leeg(waarde) and prefill:
            waarde = prefill.get(sleutel)
        if field.field_type == "checkbox":
            values[sleutel] = _as_text(waarde, "bool")
        elif field.field_type == "number":
            values[sleutel] = _as_text(waarde, "number")
        else:
            values[sleutel] = _as_text(waarde, "text")
    return values


def _form_context(media=None, prefill=None, action=None, kopie_van=None):
    prefill = prefill or {}
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
    elif prefill.get("media_type"):
        selected = next((t for t in media_types if t.code == prefill["media_type"]), None)
    if selected is None and media_types:
        selected = media_types[0]

    return {
        "media": media,
        "prefill": prefill,
        "values": _field_values(media, prefill, custom_fields),
        "form_action": action or url_for("media.add"),
        "kopie_van": kopie_van,
        "media_types": media_types,
        "owners": db.session.query(Owner).order_by(Owner.name).all(),
        "conditions": CONDITIONS,
        "custom_fields": custom_fields,
        "field_config": config,
        "current": selected.field_settings() if selected else {},
        "current_type": selected,
        # Voor de keuzelijst "nieuw op basis van een bestaand item". Alleen bij
        # het toevoegen nodig, en begrensd zodat een grote collectie de pagina
        # niet log maakt.
        "recent_items": _recent_items() if media is None else [],
    }


def _recent_items(limit=200):
    return (
        db.session.query(Media)
        .order_by(Media.id.desc())
        .limit(limit)
        .all()
    )


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
    toegelaten = ALLOWED_LOOKUP_FIELDS | {"media_type", "cover_image"}
    prefill = {k: v for k, v in request.args.items() if k in toegelaten}
    return render_template("media_form.html", **_form_context(prefill=prefill))


@media_bp.route("/<int:media_id>/edit", methods=["GET", "POST"])
def edit(media_id):
    media = db.get_or_404(Media, media_id)
    actie = url_for("media.edit", media_id=media.id)
    if request.method == "POST":
        error = _apply_form(media, request.form)
        if error:
            flash(error, "error")
            return render_template("media_form.html", **_form_context(media=media, action=actie))
        _handle_cover(media)
        db.session.commit()
        flash("Wijzigingen opgeslagen.", "success")
        return redirect(url_for("main.index"))
    return render_template("media_form.html", **_form_context(media=media, action=actie))


# ---------------------------------------------------------------------------
# Nieuw item op basis van een bestaand item
# ---------------------------------------------------------------------------
@media_bp.route("/kopie")
def copy_form():
    """
    Toont een leeg toevoegformulier dat al ingevuld is met de gegevens van een
    bestaand item. Handig bij een reeks: type, reeks, auteur, collectie,
    eigenaar, staat en je eigen velden staan meteen goed, en je vult alleen
    nog de titel en het nummer aan.

    Met `volgend=1` wordt het ook nog een stap slimmer: het reeksnummer gaat
    één omhoog en de titel blijft leeg, want het volgende album heeft
    doorgaans een andere titel.

    Het item zelf wordt hier niet aangeraakt: dit is en blijft een GET, en pas
    het formulier eronder maakt via /media/add een nieuw item aan.
    """
    bron_id = safe_int(request.args.get("bron"))
    bron = db.session.get(Media, bron_id) if bron_id else None
    if bron is None:
        flash("Kies eerst een bestaand item om van te vertrekken.", "error")
        return redirect(url_for("media.add"))

    volgend = request.args.get("volgend") in ("1", "on", "true", "ja")
    prefill = _prefill_from_media(bron, volgend=volgend)
    return render_template(
        "media_form.html",
        **_form_context(prefill=prefill, action=url_for("media.add"), kopie_van=bron),
    )


def _prefill_from_media(bron, volgend=False):
    prefill = {"media_type": bron.media_type.code if bron.media_type else ""}
    for key in COPY_FIELDS:
        waarde = getattr(bron, key, None)
        if not _leeg(waarde):
            prefill[key] = waarde
    prefill["title"] = bron.title or ""

    for sleutel, waarde in (bron.custom_fields or {}).items():
        if not _leeg(waarde):
            prefill[f"cf_{sleutel}"] = waarde

    if volgend:
        # Het volgende deel heeft een eigen titel; die laten we leeg zodat je
        # er niet per ongeluk twee keer dezelfde titel op zet.
        prefill["title"] = ""
        nummer = bron.series_number
        if nummer is not None:
            # Een special als 3.5 wordt gevolgd door 4, niet door 4.5.
            prefill["series_number"] = str(int(nummer) + 1)
        if bron.collection_number is not None:
            prefill["collection_number"] = str(bron.collection_number + 1)
    return prefill


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
    """
    Zoekt de code op bij alle externe bronnen en vult daarna aan met wat je
    zelf al in huis hebt. Die laatste stap kost niets en helpt net bij strips,
    waar de catalogi de reeks zelden invullen.
    """
    resultaat = lookup_barcode_detailed(code[:40])
    resultaat["fields"], resultaat["from_collection"] = _enrich_from_collection(resultaat["fields"])
    if resultaat["from_collection"]:
        resultaat["found"] = True
    return jsonify(resultaat)


def _enrich_from_collection(velden):
    """
    Vult reeks, nummer, auteur en collectie aan vanuit je eigen collectie.

    Vindt een catalogus wel de titel maar niet de reeks — bij stripalbums is
    dat eerder regel dan uitzondering — dan levert je eigen databank het
    antwoord vaak alsnog: staat er al een album van "De Kiekeboes" in, en komt
    die naam in de gevonden titel voor, dan is de reeks meteen bekend. Alles
    lokaal, zonder één extra netwerkaanvraag.
    """
    aangevuld = []
    titel = (velden.get("title") or "").strip()

    if titel and not velden.get("series"):
        bekende = [naam for (naam,) in db.session.query(Media.series)
                   .filter(Media.series.isnot(None), Media.series != "").distinct()]
        # Langste naam eerst: "Suske en Wiske Klassiek" gaat voor "Suske en Wiske".
        for reeks in sorted(bekende, key=len, reverse=True):
            if len(reeks) > 3 and reeks.lower() in titel.lower():
                velden["series"] = reeks
                aangevuld.append("reeks")
                if not velden.get("series_number"):
                    rest = re.sub(re.escape(reeks), " ", titel, flags=re.I)
                    nummer = re.search(r"\b(\d{1,3})\b", rest)
                    if nummer:
                        velden["series_number"] = nummer.group(1)
                        aangevuld.append("nummer")
                break

    if velden.get("series"):
        buur = (
            db.session.query(Media)
            .filter(func.lower(Media.series) == velden["series"].lower())
            .order_by(Media.id.desc())
            .first()
        )
        if buur is not None:
            if not velden.get("author") and buur.author:
                velden["author"] = buur.author
                aangevuld.append("auteur")
            if not velden.get("collection") and buur.collection:
                velden["collection"] = buur.collection
                aangevuld.append("collectie")

    return velden, aangevuld


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
    fields, _ = _enrich_from_collection(fields)
    fields["cover_image"] = name
    return render_template("photo_add.html", result=result, fields=fields, method=method)
