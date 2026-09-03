"""Databasemodellen voor de mediabeheerder."""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

CONDITIONS = [
    "slechte staat",
    "redelijke staat",
    "goede staat",
    "bijna nieuwstaat",
    "nieuwstaat",
]

# Media types die van bij de start beschikbaar zijn. Kunnen via Instellingen
# uitgebreid worden; het veld "field_profile" bepaalt welke invulvelden op
# het formulier verschijnen.
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
    # Welk vast veldenprofiel dit type gebruikt: strip | boek | cd | dvd | vrij
    field_profile = db.Column(db.String(20), nullable=False, default="vrij")

    def __repr__(self):
        return f"<MediaType {self.code}>"


class Owner(db.Model):
    __tablename__ = "owner"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Media(db.Model):
    __tablename__ = "media"
    id = db.Column(db.Integer, primary_key=True)
    media_type_id = db.Column(db.Integer, db.ForeignKey("media_type.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("owner.id"), nullable=True)

    # Gemeenschappelijke velden
    title = db.Column(db.String(300), nullable=False, default="")
    series = db.Column(db.String(300), nullable=True, default="")
    series_number = db.Column(db.Float, nullable=True)  # float zodat "3.5" (bv. specials) kan
    comment = db.Column(db.Text, nullable=True, default="")
    barcode = db.Column(db.String(64), nullable=True, index=True)
    cover_image = db.Column(db.String(300), nullable=True)

    # Strip / comic / manga / anime
    author = db.Column(db.String(200), nullable=True)  # auteur / tekenaar
    collection = db.Column(db.String(200), nullable=True)
    collection_number = db.Column(db.Integer, nullable=True)
    print_number = db.Column(db.Integer, nullable=True)
    is_duplicate = db.Column(db.Boolean, default=False)
    is_hardcover = db.Column(db.Boolean, default=False)
    condition = db.Column(db.String(30), nullable=True)

    # CD
    musician = db.Column(db.String(200), nullable=True)
    year = db.Column(db.Integer, nullable=True)

    # DVD
    audio_language = db.Column(db.String(100), nullable=True)
    subtitle_language = db.Column(db.String(100), nullable=True)

    # Waarde / extra
    estimated_value = db.Column(db.Float, nullable=True)
    custom_fields = db.Column(db.JSON, nullable=True, default=dict)

    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    media_type = db.relationship("MediaType")
    owner = db.relationship("Owner")
    loans = db.relationship("Loan", backref="media", cascade="all, delete-orphan")

    @property
    def active_loan(self):
        for loan in self.loans:
            if loan.returned_date is None:
                return loan
        return None


class Loan(db.Model):
    __tablename__ = "loan"
    id = db.Column(db.Integer, primary_key=True)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    borrower_name = db.Column(db.String(200), nullable=False)
    loan_date = db.Column(db.Date, nullable=False, default=date.today)
    returned_date = db.Column(db.Date, nullable=True)
    notified_overdue = db.Column(db.Boolean, default=False)


class Setting(db.Model):
    __tablename__ = "setting"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)


def get_setting(key, default=None):
    row = Setting.query.get(key)
    return row.value if row else default


def set_setting(key, value):
    row = Setting.query.get(key)
    if row is None:
        row = Setting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
    db.session.commit()


def seed_defaults():
    """Vult de basistabellen (media types, standaardeigenaar) als ze leeg zijn."""
    if MediaType.query.count() == 0:
        for code, label, profile in DEFAULT_MEDIA_TYPES:
            db.session.add(MediaType(code=code, label=label, field_profile=profile))
    if Owner.query.count() == 0:
        db.session.add(Owner(name="Onbekend"))
    db.session.commit()
