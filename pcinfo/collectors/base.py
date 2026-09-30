from __future__ import annotations

from ..i18n import t
from ..model import LEVEL_INFO, Report, Section
from ..utils import format_value


def add_typed(
    section: Section,
    key: str,
    value,
    kind: str,
    level: str = LEVEL_INFO,
) -> Section:
    """Add a measured value, keeping the raw number so display() can localize it.

    ``Section.add`` never fills ``raw`` on its own, so a formatted fallback string
    is stored as the value while the untouched number goes to ``raw``.
    """
    if value is None:
        return section
    return section.add(key, format_value(kind, value) or value, level=level, kind=kind, raw=value)


def add_bool(section: Section, key: str, value, level: str = LEVEL_INFO):
    """Add a tri-state flag; None means "not reported" and the field is skipped."""
    if value is None:
        return section
    return add_typed(section, key, bool(value), "bool", level)


def reading(kind: str, value, lang: str = "fr") -> str:
    """Format one measured value as text, for embedding inside a sentence."""
    if value is None:
        return ""
    return format_value(kind, value, lang) or str(value)


def add_sentence(section: Section, key: str, render, langs=("fr", "en")) -> Section:
    """Add a row whose text is built per language.

    ``render`` is called once per language so the sentence follows the UI
    language without recollecting; the default language is kept as the value.
    """
    texts = {code: render(code) for code in langs}
    texts = {code: " ".join(text.split()) for code, text in texts.items() if text}
    if not texts:
        return section
    default = texts.get("fr") or next(iter(texts.values()))
    return section.add(key, default, alts=texts)


def add_localized(section: Section, key: str, key_or_text: str, report: Report, level: str = LEVEL_INFO):
    """Add a value that is a translated sentence rather than a measurement."""
    lang = getattr(report, "lang", "fr") if report is not None else "fr"
    return section.add(key, t(key_or_text, lang), level=level)


def kilobytes(value):
    """Win32 memory fields are KiB."""
    got = float(value) if value not in (None, "") else None
    return got * 1024.0 if got is not None else None


def megabytes_to_bytes(value):
    got = float(value) if value not in (None, "") else None
    return got * 1024.0 * 1024.0 if got is not None else None


_BIT_UNITS = ((1e12, "Tbit/s"), (1e9, "Gbit/s"), (1e6, "Mbit/s"), (1e3, "Kbit/s"))


def rate(bits_per_second, lang: str = "fr"):
    """Format a bit rate; there is no 'bits' kind in format_value."""
    from ..utils import num

    value = float(bits_per_second or 0)
    if value <= 0:
        return None
    for scale, unit in _BIT_UNITS:
        if value >= scale:
            return f"{num(value / scale, 1, lang)} {unit}"
    return f"{num(value, 0, lang)} bit/s"
