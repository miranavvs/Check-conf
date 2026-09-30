from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from typing import Callable

from ..model import Report, Section
from ..utils import IS_WINDOWS
from . import win, windows

Collector = Callable[[Report, bool], "Section | None"]


@dataclass(frozen=True)
class Spec:
    key: str
    icon: str
    label: str
    collect: Collector
    deep: bool = False


SPECS: tuple[Spec, ...] = (
    Spec("system", "system", "sec.system", windows.system),
    Spec("cpu", "cpu", "sec.cpu", windows.cpu),
    Spec("memory", "memory", "sec.memory", windows.memory),
    Spec("gpu", "gpu", "sec.gpu", windows.gpu),
    Spec("sound", "sound", "sec.sound", windows.sound),
    Spec("board", "board", "sec.board", windows.board),
    Spec("bios", "bios", "sec.bios", windows.bios),
    Spec("disk", "disk", "sec.disk", windows.disk),
    Spec("partitions", "partitions", "sec.partitions", windows.partitions),
    Spec("network", "network", "sec.network", windows.network),
    Spec("wifi", "wifi", "sec.wifi", windows.wifi),
    Spec("display", "display", "sec.display", windows.display),
    Spec("battery", "battery", "sec.battery", windows.battery),
    Spec("temp", "temp", "sec.temp", windows.temp),
    Spec("usb", "usb", "sec.usb", windows.usb, deep=True),
    Spec("load", "load", "sec.load", windows.load),
)

SPECS_BY_KEY = {spec.key: spec for spec in SPECS}


def keys(deep: bool = True) -> list[str]:
    return [spec.key for spec in SPECS if deep or not spec.deep]


def spec_for(key: str) -> Spec | None:
    return SPECS_BY_KEY.get(key)


def collect_report(
    deep: bool = False,
    lang: str = "fr",
    progress: Callable[[str], None] | None = None,
) -> Report:
    started = time.perf_counter()
    report = Report(deep=deep, lang=lang)
    if not IS_WINDOWS:
        return report
    win.snapshot(deep=deep)
    for spec in SPECS:
        if spec.deep and not deep:
            continue
        if progress is not None:
            progress(spec.key)
        try:
            section = spec.collect(report, deep)
        except Exception:
            section = Section(spec.key, spec.icon)
            section.error = traceback.format_exc(limit=3).strip().splitlines()[-1]
        if section is not None and (section.fields or section.error):
            report.sections.append(section)
    report.duration = time.perf_counter() - started
    return report
