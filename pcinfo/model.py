from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .utils import format_value

LEVEL_INFO = "info"
LEVEL_WARN = "warn"
LEVEL_BAD = "bad"

DROP_VALUES = {"", "-", "--", "n/a", "na", "none", "null", "nil", "unknown", "(null)"}


@dataclass
class Field:
    key: str
    value: str
    level: str = LEVEL_INFO
    kind: str = "text"
    raw: object = None
    alts: dict | None = None

    def display(self, lang: str = "fr") -> str:
        if self.alts and lang in self.alts:
            return self.alts[lang]
        if self.kind == "text" or self.raw is None:
            return self.value
        return format_value(self.kind, self.raw, lang) or self.value


@dataclass
class Section:
    key: str
    icon: str
    fields: list = field(default_factory=list)
    error: str | None = None

    def add(self, key, value, level=LEVEL_INFO, kind="text", raw=None, alts=None):
        if value is None or key in DROP_VALUES:
            return self
        if not isinstance(value, str):
            value = str(value)
        value = " ".join(value.split()) if kind == "text" else value.strip()
        if value.lower() in DROP_VALUES:
            return self
        self.fields.append(Field(key, value, level, kind, raw, alts))
        return self

    def add_many(self, pairs, level=LEVEL_INFO):
        for key, value in pairs:
            self.add(key, value, level)
        return self

    def absorb(self, other, skip_duplicates=True):
        if other is None:
            return self
        existing = {f.key for f in self.fields}
        for item in other.fields:
            if skip_duplicates and item.key in existing:
                continue
            self.fields.append(item)
            existing.add(item.key)
        return self

    def is_empty(self) -> bool:
        return not self.fields


@dataclass
class Report:
    sections: list = field(default_factory=list)
    hostname: str = ""
    os_label: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    deep: bool = False
    lang: str = "fr"

    def get(self, key):
        for section in self.sections:
            if section.key == key:
                return section
        return None
