"""Uitleenmodule: registreren, terugbrengen en waarschuwen."""
from datetime import date, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from extensions import db
from models import Loan, Media, get_setting
from security import clean_text, safe_int
from services.ha_integration import push_ha_notification
from services.jobs import OVERDUE_DAYS

lending_bp = Blueprint("lending", __name__, url_prefix="/uitleen")


@lending_bp.route("/")
def index():
    today = date.today()
    active = (
        db.session.query(Loan)
        .options(joinedload(Loan.media))
        .filter(Loan.returned_date.is_(None))
        .order_by(Loan.loan_date)
        .all()
    )
    for loan in active:
        loan.days_out = (today - loan.loan_date).days
        loan.is_overdue = loan.days_out > OVERDUE_DAYS

    history = (
        db.session.query(Loan)
        .options(joinedload(Loan.media))
        .filter(Loan.returned_date.isnot(None))
        .order_by(Loan.returned_date.desc())
        .limit(50)
        .all()
    )

    lent_ids = {loan.media_id for loan in active}
    available = [
        m for m in db.session.query(Media).order_by(Media.title).all()
        if m.id not in lent_ids
    ]

    return render_template(
        "lending.html",
        active_loans=active,
        history=history,
        available_media=available,
        today=today.isoformat(),
        overdue_days=OVERDUE_DAYS,
        ha_configured=bool(get_setting("ha_url") and get_setting("ha_token")),
    )


@lending_bp.route("/add", methods=["POST"])
def add():
    media_id = safe_int(request.form.get("media_id"))
    borrower = clean_text(request.form.get("borrower_name"), 200)
    if not media_id or not db.session.get(Media, media_id):
        flash("Kies een geldig item.", "error")
        return redirect(url_for("lending.index"))
    if not borrower:
        flash("De naam van de ontlener is verplicht.", "error")
        return redirect(url_for("lending.index"))

    try:
        loan_date = date.fromisoformat(request.form.get("loan_date") or date.today().isoformat())
    except ValueError:
        loan_date = date.today()
    if loan_date > date.today() + timedelta(days=1):
        loan_date = date.today()

    db.session.add(Loan(media_id=media_id, borrower_name=borrower, loan_date=loan_date))
    db.session.commit()
    flash("Uitlening geregistreerd.", "success")
    return redirect(url_for("lending.index"))


@lending_bp.route("/<int:loan_id>/return", methods=["POST"])
def mark_returned(loan_id):
    loan = db.get_or_404(Loan, loan_id)
    loan.returned_date = date.today()
    db.session.commit()
    flash("Als teruggebracht gemarkeerd.", "success")
    return redirect(url_for("lending.index"))


@lending_bp.route("/<int:loan_id>/remind", methods=["POST"])
def remind(loan_id):
    """Stuurt meteen een herinnering naar Home Assistant."""
    loan = db.get_or_404(Loan, loan_id)
    ok, error = push_ha_notification(
        get_setting("ha_url"),
        get_setting("ha_token"),
        title="Media te lang uitgeleend",
        message=f"'{loan.media.title}' is sinds {loan.loan_date} uitgeleend aan {loan.borrower_name}.",
    )
    return jsonify({"ok": ok, "error": error})
