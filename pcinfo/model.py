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
    group: str = ""

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

    def __post_init__(self):
        self._group = ""

    def group(self, name: str = ""):
        """Set the group applied to every following field (order-preserving)."""
        self._group = name or ""
        return self

    def add(self, key, value, level=LEVEL_INFO, kind="text", raw=None, alts=None, group=None):
        if value is None or key in DROP_VALUES:
            return self
        if not isinstance(value, str):
            value = str(value)
        value = " ".join(value.split()) if kind == "text" else value.strip()
        if value.lower() in DROP_VALUES:
            return self
        self.fields.append(Field(key, value, level, kind, raw, alts, self._group if group is None else group))
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

    def field(self, key):
        for section in self.sections:
            for item in section.fields:
                if item.key == key:
                    return item
        return None


def group_fields(fields) -> list:
    """Split fields into ordered (group, [fields]) runs, preserving order."""
    out: list = []
    for item in fields:
        name = getattr(item, "group", "") or ""
        if out and out[-1][0] == name:
            out[-1][1].append(item)
        else:
            out.append((name, [item]))
    return out


def distinct_groups(fields) -> list:
    seen: list = []
    for item in fields:
        name = getattr(item, "group", "") or ""
        if name and name not in seen:
            seen.append(name)
    return seen


SUMMARY = (
    ("pc.brand", "sum.pc"),
    ("cpu.name", "sum.cpu"),
    ("mem.total", "sum.mem"),
    ("gpu.name", "sum.gpu"),
    ("os", "sum.os"),
)

_VIRTUAL_HINTS = ("virtual", "basic display", "remote", "parsec", "idd", "spacedesk")


def summary_field(report: "Report", key: str):
    """Pick the field for a summary slot, preferring a physical GPU over a virtual one."""
    fields = [item for section in report.sections for item in section.fields if item.key == key]
    if not fields:
        return None
    if key == "gpu.name":
        real = [item for item in fields if not any(hint in item.value.casefold() for hint in _VIRTUAL_HINTS)]
        if real:
            return real[0]
    return fields[0]
