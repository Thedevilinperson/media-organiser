"""Hulpfuncties voor de basisweergave: zoeken, filteren en sorteren."""

SEARCHABLE = (
    "title", "series", "author", "musician", "collection",
    "comment", "barcode", "condition", "audio_language", "subtitle_language",
)


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
    return False


def matches_filters(media, filters, ignore=None):
    """
    Controleert of een item aan de gekozen filters voldoet. Met 'ignore' laat
    je één filter buiten beschouwing: zo bouwen we de keuzelijst van dat
    filter op met alles wat nog mogelijk is (vereiste 1.a).
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


def sort_key(media):
    """
    Strips, comics, manga en anime: alfabetisch op reeks, dan op nummer
    (vereiste 1.a.iv). Alle andere types op titel.
    """
    if media.profile == "strip":
        return (0, (media.series or "zzz").lower(), media.series_number if media.series_number is not None else 0, (media.title or "").lower())
    return (1, (media.title or "").lower(), 0, "")
