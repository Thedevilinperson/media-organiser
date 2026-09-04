"""Achtergrondtaken: dagelijkse controle op te lang uitgeleende media."""
from datetime import date, timedelta

from extensions import db
from models import Loan, Media, get_setting
from services.ha_integration import push_ha_notification

OVERDUE_DAYS = 30


def check_overdue_loans_job(app):
    """
    Zoekt uitleningen ouder dan een maand waarvoor nog geen melding
    verstuurd is en pusht die naar Home Assistant. Draait één keer per dag,
    zodat de achtergrondtaak nagenoeg geen belasting geeft (vereiste 3c).
    """
    with app.app_context():
        ha_url = get_setting("ha_url")
        ha_token = get_setting("ha_token")
        if not ha_url or not ha_token:
            return

        cutoff = date.today() - timedelta(days=OVERDUE_DAYS)
        overdue = (
            db.session.query(Loan)
            .filter(
                Loan.returned_date.is_(None),
                Loan.loan_date <= cutoff,
                Loan.notified_overdue.is_(False),
            )
            .all()
        )
        if not overdue:
            return

        for loan in overdue:
            media = db.session.get(Media, loan.media_id)
            title = media.title if media else "onbekende titel"
            ok, _ = push_ha_notification(
                ha_url,
                ha_token,
                title="Media te lang uitgeleend",
                message=(
                    f"'{title}' is sinds {loan.loan_date} uitgeleend aan "
                    f"{loan.borrower_name} — meer dan een maand geleden."
                ),
            )
            if ok:
                loan.notified_overdue = True
        db.session.commit()
