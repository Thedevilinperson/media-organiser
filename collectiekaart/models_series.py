"""
Los model voor de reeksencontrole bij De Poort.

Bewust in een apart bestand in plaats van toegevoegd aan models.py: zo hoeft
een bestaand, werkend bestand niet aangeraakt te worden voor één nieuwe tabel.
Wordt geregistreerd bij SQLAlchemy door dit bestand simpelweg te importeren
(zie app.py) voordat db.create_all() draait; de tabel zelf komt er dan vanzelf
bij, net als bij elk ander nieuw model.
"""
from extensions import db


class SeriesCheck(db.Model):
    """
    Laatste resultaat van de controle bij De Poort voor één reeks: bestaan er
    nummers die niet in de collectie zitten? Wordt bijgewerkt door de
    wekelijkse achtergrondtaak en door de knop "Controleer nu" bij Reeksen.
    Zonder deze tabel zou dat resultaat verdwijnen zodra de pagina herladen
    wordt, en zou elke klik op de knop de website van De Poort opnieuw moeten
    raadplegen ook voor reeksen die net al gecontroleerd zijn.
    """
    __tablename__ = "series_check"

    series = db.Column(db.String(300), primary_key=True)
    checked_at = db.Column(db.DateTime, nullable=True)
    ok = db.Column(db.Boolean, nullable=True)
    new_numbers = db.Column(db.JSON, nullable=True)
    message = db.Column(db.Text, nullable=True)
