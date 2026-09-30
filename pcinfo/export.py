from __future__ import annotations

import html
import json
import os

from .i18n import t
from .icons import accent
from .model import Report
from .theme import BG, BORDER, MUTED, SURFACE, TEXT, WARN, level_color
from .utils import human_datetime

_WIDTH = 28


def _meta(report: Report, lang: str) -> list[str]:
    lines = [
        f"{t('report.generated', lang)} : {human_datetime(report.generated_at, lang)}",
        f"{t('report.duration', lang)} : {report.duration:.2f} s",
    ]
    if report.deep:
        lines.append(f"{t('report.deep', lang)} : {t('value.yes', lang)}")
    if report.hostname or report.os_label:
        lines.append(f"{report.hostname} — {report.os_label}".strip(" —"))
    return lines


def _head(report: Report, lang: str) -> list[str]:
    return [t("app.name", lang), t("report.title", lang), *_meta(report, lang)]


def to_text(report: Report, lang: str = "fr") -> str:
    lines = _head(report, lang)
    for section in report.sections:
        lines.append("")
        lines.append(f"== {t(f'sec.{section.key}', lang)} ==")
        for item in section.fields:
            key = t(f"f.{item.key}", lang)
            value = item.display(lang)
            lines.append(f"{key.ljust(_WIDTH)}: {value}")
        if section.error:
            lines.append(f"{'!':.ljust(_WIDTH)}: {section.error}")
    return "\n".join(lines) + "\n"


def to_dict(report: Report, lang: str = "fr") -> dict:
    return {
        "app": t("app.name", lang),
        "title": t("report.title", lang),
        "generated_at": report.generated_at.isoformat(timespec="seconds"),
        "duration_seconds": round(report.duration, 3),
        "deep": report.deep,
        "hostname": report.hostname,
        "os": report.os_label,
        "sections": [
            {
                "key": section.key,
                "title": t(f"sec.{section.key}", lang),
                "error": section.error,
                "fields": [
                    {
                        "key": item.key,
                        "label": t(f"f.{item.key}", lang),
                        "value": item.display(lang),
                        "raw": item.raw,
                        "kind": item.kind,
                        "level": item.level,
                    }
                    for item in section.fields
                ],
            }
            for section in report.sections
        ],
    }


def to_json(report: Report, lang: str = "fr") -> str:
    return json.dumps(to_dict(report, lang), ensure_ascii=False, indent=2) + "\n"


_HTML_CSS = f"""
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 34px 26px 60px; background: {BG}; color: {TEXT};
    font-family: "Segoe UI", Inter, sans-serif; font-size: 14px; line-height: 1.5; }}
h1 {{ margin: 0 0 2px; font-size: 24px; font-weight: 650; }}
h2 {{ margin: 0; font-size: 15px; font-weight: 600; }}
.sub {{ color: {MUTED}; font-size: 12px; margin: 0 0 6px; }}
.meta {{ color: {MUTED}; font-size: 12px; margin: 0 0 24px; }}
.meta b {{ color: {TEXT}; font-weight: 500; }}
.grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }}
.card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; padding: 15px 17px; }}
.card > header {{ display: flex; align-items: center; gap: 9px; margin-bottom: 11px;
    padding-bottom: 10px; border-bottom: 1px solid {BORDER}; }}
.dot {{ width: 9px; height: 9px; border-radius: 50%; flex: none; }}
.count {{ margin-left: auto; color: {MUTED}; font-size: 11px; background: rgba(255,255,255,.05);
    border-radius: 8px; padding: 2px 8px; }}
dl {{ display: grid; grid-template-columns: minmax(96px, 40%) 1fr; gap: 6px 14px; margin: 0; }}
dt {{ color: {MUTED}; overflow-wrap: anywhere; }}
dd {{ margin: 0; font-weight: 500; overflow-wrap: anywhere; }}
.err {{ color: {WARN}; font-size: 12px; margin-top: 10px; }}
@media print {{
  body {{ background: #fff; color: #111; padding: 0; }}
  .card {{ break-inside: avoid; border-color: #ccc; background: #fff; }}
  dt, .sub, .meta, .count {{ color: #555; }}
  dd {{ color: #111; }}
}}
"""


def to_html(report: Report, lang: str = "fr") -> str:
    cards = []
    for section in report.sections:
        rows = "".join(
            f"<dt>{html.escape(t(f'f.{item.key}', lang))}</dt>"
            f"<dd style=\"color:{level_color(item.level)}\">{html.escape(item.display(lang))}</dd>"
            for item in section.fields
        )
        error = (
            f'<p class="err">{html.escape(section.error)}</p>' if section.error else ""
        )
        cards.append(
            f'<section class="card"><header>'
            f'<span class="dot" style="background:{accent(section.icon)}"></span>'
            f"<h2>{html.escape(t(f'sec.{section.key}', lang))}</h2>"
            f'<span class="count">{html.escape(t("section.count", lang).format(n=len(section.fields)))}</span>'
            f"</header><dl>{rows}</dl>{error}</section>"
        )

    meta = " &nbsp;·&nbsp; ".join(html.escape(line) for line in _meta(report, lang))
    body = "".join(
        [
            f"<h1>{html.escape(t('app.name', lang))}</h1>",
            f'<p class="sub">{html.escape(t("app.subtitle", lang))}</p>',
            f'<p class="meta">{meta}</p>',
            f'<div class="grid">{"".join(cards)}</div>',
        ]
    )
    return (
        "<!doctype html>\n"
        f'<html lang="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(t('report.title', lang))}</title>"
        f"<style>{_HTML_CSS}</style></head><body>{body}</body></html>\n"
    )


def _accent_for(icon: str) -> str:
    return accent(icon)


WRITERS = {".txt": to_text, ".json": to_json, ".html": to_html}


def write_report(report: Report, path: str, lang: str = "fr") -> str:
    ext = os.path.splitext(path)[1].lower()
    writer = WRITERS.get(ext)
    if writer is None:
        raise ValueError(f"unsupported extension: {ext or path}")
    text = writer(report, lang)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


__all__ = ["to_dict", "to_html", "to_json", "to_text", "write_report"]
