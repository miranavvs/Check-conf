from __future__ import annotations

import locale
import os
import platform
import re
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

_BYTE_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
_HZ_UNITS = ("Hz", "kHz", "MHz", "GHz", "THz")

_ENCODINGS = ("utf-8", "cp1252", "cp850", "cp437", "latin-1")


def _decode(data) -> str:
    if isinstance(data, str):
        return data
    if not data:
        return ""
    candidates = ["utf-8", locale.getpreferredencoding(False), *_ENCODINGS]
    seen = set()
    for enc in candidates:
        if not enc or enc.lower() in seen:
            continue
        seen.add(enc.lower())
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError, ValueError):
            continue
    return data.decode("utf-8", "replace")


def num(value, digits=1, lang="fr") -> str:
    text = f"{float(value):.{digits}f}"
    return text.replace(".", ",") if lang == "fr" else text


def format_value(kind, raw, lang="fr"):
    if raw is None:
        return None
    try:
        if kind == "bytes":
            value = float(raw)
            for unit in _BYTE_UNITS:
                if abs(value) < 1024.0 or unit == _BYTE_UNITS[-1]:
                    return f"{num(value, 0 if unit == 'B' else 1, lang)} {unit}"
                value /= 1024.0
            return None
        if kind == "hz":
            value = float(raw)
            for unit in _HZ_UNITS:
                if abs(value) < 1000.0 or unit == _HZ_UNITS[-1]:
                    return f"{num(value, 0 if unit == 'Hz' else 2, lang)} {unit}"
                value /= 1000.0
            return None
        if kind == "percent":
            return f"{num(raw, 1, lang)} %"
        if kind == "temp":
            return f"{num(raw, 1, lang)} °C"
        if kind == "int":
            count = int(raw)
            if lang == "fr":
                return f"{count:,}".replace(",", "\u202f")
            return f"{count:,}"
        if kind == "duration":
            return human_duration(float(raw), lang)
        if kind == "mult":
            return f"x{num(raw, 1, lang)}"
        if kind == "bool":
            from .i18n import t

            return t("value.yes" if raw else "value.no", lang)
        if kind == "volt":
            return f"{num(raw, 2, lang)} V"
        if kind == "mah":
            return f"{float(raw):,.0f}".replace(",", "\u202f") + " mAh"
        if kind == "wh":
            return f"{num(raw, 1, lang)} Wh"
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def human_duration(seconds, lang="fr") -> str:
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    if total < 0:
        total = 0
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    fr = lang == "fr"
    parts = []
    if days:
        parts.append(f"{days} j" if fr else f"{days} d")
    if days or hours:
        parts.append(f"{hours} h")
    if days or hours or minutes:
        parts.append(f"{minutes} min")
    parts.append(f"{secs} s")
    return " ".join(parts)


def human_datetime(value, lang="fr") -> str:
    if value is None:
        return ""
    try:
        if lang == "fr":
            return value.strftime("%d/%m/%Y %H:%M")
        return value.strftime("%Y-%m-%d %H:%M")
    except (AttributeError, ValueError):
        return str(value)


def run(cmd, timeout=25, shell=False, env=None) -> str:
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "timeout": timeout,
        "shell": shell,
    }
    if IS_WINDOWS and not shell:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    merged = None
    if env:
        merged = dict(os.environ)
        merged.update(env)
        kwargs["env"] = merged
    try:
        proc = subprocess.run(cmd, **kwargs)
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    if proc.returncode != 0 and not (proc.stdout or b"").strip():
        return ""
    return _decode(proc.stdout)


def which(name) -> str:
    return shutil.which(name) or ""


def has(name) -> bool:
    return bool(which(name))


def read_text(path, limit=None) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            data = handle.read() if limit is None else handle.read(limit)
        return data
    except OSError:
        return ""


def to_int(value, default=0) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace("\u00a0", " ")
    match = re.search(r"-?\d[\d\s.,]*", text)
    if not match:
        return default
    digits = re.sub(r"[^\d-]", "", match.group(0).replace(" ", ""))
    if digits in ("", "-"):
        return default
    try:
        return int(digits)
    except ValueError:
        return default


def to_float(value, default=0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\u00a0", " ").replace(",", ".")
    match = re.search(r"-?\d[\d\s.]*", text)
    if not match:
        return default
    cleaned = re.sub(r"[^\d.]", "", match.group(0).replace(" ", ""))
    if not cleaned:
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def clean_lines(text) -> list:
    if not text:
        return []
    return [line.rstrip() for line in str(text).splitlines() if line.strip()]


def parse_kv(text, sep=":", lowercase=True) -> dict:
    out = {}
    for line in clean_lines(text):
        if sep not in line:
            continue
        key, _, value = line.partition(sep)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        if lowercase:
            key = key.lower()
        out[key] = value
    return out


def getmac(address) -> str:
    if not address:
        return ""
    parts = [p for p in str(address).split(":") if p]
    if len(parts) != 6:
        return ""
    return ":".join(p.lower().rjust(2, "0") for p in parts)


def clean_iface(value) -> str:
    return str(value or "").split("%", 1)[0]


def bool_text(value, lang="fr") -> str:
    if lang == "fr":
        return "Oui" if value else "Non"
    return "Yes" if value else "No"


def system_fingerprint() -> str:
    parts = [platform.system(), platform.release(), platform.machine(), platform.node()]
    return " ".join(p for p in parts if p)


def first_line(text) -> str:
    lines = clean_lines(text)
    return lines[0].strip() if lines else ""


def squash(text, limit=140) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "\u2026"


def powershell(script, timeout=40):
    exe = "powershell"
    if IS_WINDOWS and has("pwsh"):
        exe = "pwsh"
    wrapped = f"[Console]::OutputEncoding=[Text.Encoding]::UTF8\n{ps_encode(script)}"
    return run([exe, "-NoProfile", "-NonInteractive", "-Command", wrapped], timeout=timeout)


def ps_encode(text) -> str:
    return str(text).encode("utf-8", "replace").decode("utf-8", "replace")
