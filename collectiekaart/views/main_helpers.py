"""Hulpfuncties voor het overzicht en de volledige lijst: zoeken, filteren, sorteren."""

SEARCHABLE = (
    "title", "series", "author", "musician", "collection",
    "comment", "barcode", "condition", "audio_language", "subtitle_language",
)

# Welke kolommen het overzicht per veldenprofiel toont, en waarop er binnen dat
# profiel gesorteerd wordt. Bewust kort gehouden: op een telefoon moet een rij
# in één oogopslag leesbaar zijn.
# Bij strips staat het nummer vooraan. Op een telefoon is dat de smalste kolom
# en meteen het gegeven waarop je zoekt binnen een reeks; stond de reeks eerst,
# dan duwde een lange reeksnaam de titel van het scherm.
PROFILE_COLUMNS = {
    "strip": ["Nr.", "Reeks", "Titel"],
    "boek": ["Auteur", "Titel"],
    "cd": ["Muzikant", "Titel", "Jaar"],
    "dvd": ["Titel", "Jaar"],
    "vrij": ["Titel"],
}


def _lower(value):
    return (value or "").lower()


def matches_search(media, term):
    """Zoekt over alle kolommen heen (vereiste 1.a.ii)."""
    if not term:
        return True
    term = term.lower()
    for field in SEARCHABLE:
        value = getattr(media, field, None)
        if value and term in str(value).lower():
            return True
    if media.series_number is not None and term in str(media.series_number):
        return True
    if media.year and term in str(media.year):
        return True
    if media.owner and term in media.owner.name.lower():
        return True
    if media.media_type and term in media.media_type.label.lower():
        return True
    for value in (media.custom_fields or {}).values():
        if value and term in str(value).lower():
            return True
    return False


def matches_filters(media, filters, ignore=None):
    """
    Controleert of een item aan de gekozen filters voldoet. Met 'ignore' laat
    je één filter buiten beschouwing: zo bouwen we de keuzelijst van dat filter
    op met alles wat nog mogelijk is (vereiste 1.a).
    """
    if filters.get("type") and ignore != "type":
        if not media.media_type or media.media_type.code != filters["type"]:
            return False
    if filters.get("owner") and ignore != "owner":
        if not media.owner or media.owner.name != filters["owner"]:
            return False
    if filters.get("series") and ignore != "series":
        if (media.series or "") != filters["series"]:
            return False
    if filters.get("title") and ignore != "title":
        if (media.title or "") != filters["title"]:
            return False
    return True


def profile_sort_key(media):
    """
    Sorteert binnen een type volgens wat voor dat type logisch is:
    strips op reeks en dan op nummer, boeken op auteur en dan op titel,
    cd's op muzikant, de rest op titel.
    """
    profile = media.profile
    if profile == "strip":
        return (
            _lower(media.series) or "zzzz",
            media.series_number if media.series_number is not None else 0,
            _lower(media.title),
        )
    if profile == "boek":
        return (_lower(media.author) or "zzzz", _lower(media.title), 0)
    if profile == "cd":
        return (_lower(media.musician or media.author) or "zzzz", _lower(media.title), 0)
    return (_lower(media.title), "", 0)


def sort_key(media):
    """Volgorde voor de volledige lijst, waar alle types door elkaar staan."""
    if media.profile == "strip":
        return (0, _lower(media.series) or "zzzz",
                media.series_number if media.series_number is not None else 0,
                _lower(media.title))
    return (1, _lower(media.title), 0, "")


def group_by_type(items):
    """
    Bundelt de items per mediatype, elk met de kolommen en de volgorde die bij
    dat type horen. Types staan alfabetisch.
    """
    groups = {}
    for media in items:
        label = media.media_type.label if media.media_type else "Onbekend"
        group = groups.setdefault(label, {
            "label": label,
            "profile": media.profile,
            "columns": PROFILE_COLUMNS.get(media.profile, PROFILE_COLUMNS["vrij"]),
            # Bewust "rows" en niet "items": in een sjabloon botst de naam
            # items met de ingebouwde methode van een dictionary.
            "rows": [],
        })
        group["rows"].append(media)

    for group in groups.values():
        group["rows"].sort(key=profile_sort_key)
    return [groups[label] for label in sorted(groups, key=str.lower)]
