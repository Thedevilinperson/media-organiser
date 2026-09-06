"""
Achtergrondtaken: dagelijkse controle op te lang uitgeleende media, en de
wekelijkse (of handmatige) controle bij De Poort op nieuwe nummers per reeks.
"""
import time
from datetime import date, datetime, timedelta

from extensions import db
from models import Loan, Media, MediaType, get_setting, set_setting
from models_series import SeriesCheck
from services.ha_integration import push_ha_notification
from services.series_analysis import check_new_releases, missing_numbers_per_series

OVERDUE_DAYS = 30

# Profielen waarvoor een reeksanalyse zinvol is (dezelfde als in
# views/analysis.py; hier apart gehouden zodat deze module op zichzelf staat).
SERIES_PROFILES = ("strip", "boek")

# Pauze tussen twee aanvragen aan De Poort. Die website is een gewone
# webwinkel, geen API: tientallen aanvragen kort na elkaar zou op hun server
# overkomen als een aanval in plaats van een gewone bezoeker. Bij een
# collectie met veel reeksen duurt de controle daardoor bewust enkele
# minuten; dat is geen storing.
SERIES_CHECK_DELAY = 3


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


def run_series_check(app):
    """
    Doorloopt elke reeks in de collectie en vraagt bij De Poort na of er
    nummers bestaan die nog niet in de collectie zitten. Wordt zowel
    wekelijks automatisch aangeroepen (app.py) als op vraag via de knop bij
    Reeksen (views/analysis.py); beide roepen gewoon deze functie aan zodat
    de vertraging tussen aanvragen op precies één plek geregeld is.

    Draait typisch enkele minuten voor een collectie met veel reeksen, door
    SERIES_CHECK_DELAY hierboven. Om te voorkomen dat de wekelijkse taak en
    een handmatige klik elkaar overlappen — wat dubbel zoveel aanvragen naar
    De Poort zou sturen — controleert en zet deze functie zelf een vlag in de
    instellingen zolang ze loopt.
    """
    with app.app_context():
        if get_setting("series_check_running") == "1":
            return

        set_setting("series_check_running", "1")
        try:
            items = (
                db.session.query(Media)
                .join(MediaType)
                .filter(MediaType.field_profile.in_(SERIES_PROFILES))
                .filter(Media.series.isnot(None), Media.series_number.isnot(None))
                .all()
            )
            rows = missing_numbers_per_series(items)

            for index, row in enumerate(rows):
                if index > 0:
                    time.sleep(SERIES_CHECK_DELAY)

                result = check_new_releases(row["series"], row["owned"])

                check = db.session.get(SeriesCheck, row["series"])
                if check is None:
                    check = SeriesCheck(series=row["series"])
                    db.session.add(check)
                check.checked_at = datetime.utcnow()
                check.ok = result["ok"]
                check.new_numbers = result.get("new_numbers") or []
                check.message = result.get("error") or result.get("note")
                db.session.commit()
        finally:
            set_setting("series_check_running", "")
