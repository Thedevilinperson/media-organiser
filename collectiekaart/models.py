"""Databasemodellen voor de mediabeheerder."""
from datetime import date, datetime

from extensions import db

CONDITIONS = [
    "slechte staat",
    "redelijke staat",
    "goede staat",
    "bijna nieuwstaat",
    "nieuwstaat",
]

# Veldenprofielen bepalen welke invulvelden op het formulier verschijnen.
FIELD_PROFILES = {
    "strip": "strip / comic / manga / anime",
    "boek": "boek",
    "cd": "cd",
    "dvd": "dvd",
    "vrij": "vrij (titel + commentaar)",
}

DEFAULT_MEDIA_TYPES = [
    ("strip", "Strip", "strip"),
    ("comic", "Comic", "strip"),
    ("manga", "Manga", "strip"),
    ("anime", "Anime", "strip"),
    ("boek", "Boek", "boek"),
    ("cd", "CD", "cd"),
    ("dvd", "DVD", "dvd"),
]


class MediaType(db.Model):
    __tablename__ = "media_type"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    field_profile = db.Column(db.String(20), nullable=False, default="vrij")

    custom_fields = db.relationship(
        "CustomField", backref="media_type", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MediaType {self.code}>"


class CustomField(db.Model):
    """
    Eigen veld dat een gebruiker via Instellingen kan toevoegen (vereiste
    1.f.iv: velden aanpassen). De waarde zelf wordt in Media.custom_fields
    (JSON) bewaard, zodat er geen schemawijziging nodig is per nieuw veld.
    """
    __tablename__ = "custom_field"
    id = db.Column(db.Integer, primary_key=True)
    media_type_id = db.Column(db.Integer, db.ForeignKey("media_type.id"), nullable=True)
    key = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(20), nullable=False, default="text")  # text|number|checkbox


class Owner(db.Model):
    __tablename__ = "owner"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Media(db.Model):
    __tablename__ = "media"
    id = db.Column(db.Integer, primary_key=True)
    media_type_id = db.Column(db.Integer, db.ForeignKey("media_type.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("owner.id"), nullable=True)

    # Gemeenschappelijk
    title = db.Column(db.String(300), nullable=False, default="")
    series = db.Column(db.String(300), nullable=True, index=True)
    series_number = db.Column(db.Float, nullable=True)  # float: laat specials als 3.5 toe
    comment = db.Column(db.Text, nullable=True)
    barcode = db.Column(db.String(64), nullable=True, index=True)
    cover_image = db.Column(db.String(300), nullable=True)

    # Strip / comic / manga / anime / boek
    author = db.Column(db.String(200), nullable=True)
    collection = db.Column(db.String(200), nullable=True)
    collection_number = db.Column(db.Integer, nullable=True)
    print_number = db.Column(db.Integer, nullable=True)
    is_duplicate = db.Column(db.Boolean, default=False, nullable=False)
    is_hardcover = db.Column(db.Boolean, default=False, nullable=False)
    condition = db.Column(db.String(30), nullable=True)

    # CD
    musician = db.Column(db.String(200), nullable=True)
    year = db.Column(db.Integer, nullable=True)

    # DVD
    audio_language = db.Column(db.String(100), nullable=True)
    subtitle_language = db.Column(db.String(100), nullable=True)

    # Waarde en eigen velden
    estimated_value = db.Column(db.Float, nullable=True)
    value_source = db.Column(db.String(50), nullable=True)  # manueel | lastdodo
    custom_fields = db.Column(db.JSON, nullable=True, default=dict)

    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    media_type = db.relationship("MediaType")
    owner = db.relationship("Owner")
    loans = db.relationship("Loan", backref="media", cascade="all, delete-orphan")

    @property
    def profile(self):
        return self.media_type.field_profile if self.media_type else "vrij"

    @property
    def active_loan(self):
        for loan in self.loans:
            if loan.returned_date is None:
                return loan
        return None

    @property
    def creator(self):
        """Auteur/tekenaar, of muzikant bij een cd."""
        return self.author or self.musician


class Loan(db.Model):
    __tablename__ = "loan"
    id = db.Column(db.Integer, primary_key=True)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    borrower_name = db.Column(db.String(200), nullable=False)
    loan_date = db.Column(db.Date, nullable=False, default=date.today)
    returned_date = db.Column(db.Date, nullable=True)
    notified_overdue = db.Column(db.Boolean, default=False, nullable=False)


class Setting(db.Model):
    __tablename__ = "setting"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)


def get_setting(key, default=None):
    row = db.session.get(Setting, key)
    return row.value if row and row.value is not None else default


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row is None:
        db.session.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.session.commit()


def seed_defaults():
    """Vult de basistabellen als ze nog leeg zijn."""
    if db.session.query(MediaType).count() == 0:
        for code, label, profile in DEFAULT_MEDIA_TYPES:
            db.session.add(MediaType(code=code, label=label, field_profile=profile))
    if db.session.query(Owner).count() == 0:
        db.session.add(Owner(name="Onbekend"))
    db.session.commit()
