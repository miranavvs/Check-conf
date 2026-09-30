# CheckConf — Config PC

A Windows desktop app that collects a full hardware and system inventory, then
exports it as a text, JSON or HTML report.

Built with Python and PySide6. No admin rights required, no registry writes, no
network calls. Everything is read locally.

![PySide6](https://img.shields.io/badge/PySide6-6.11.2-4c8dff) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

15 sections collected in a single pass, around 6 seconds:

| Section | What it reports |
|---|---|
| System | OS, build, edition, uptime, install date, timezone, hypervisor |
| Processor | Model, cores, threads, base/max/current frequency, caches, load |
| Memory | Installed, used, available, usage rate, slots, swap |
| Graphics | Model, dedicated and shared VRAM, driver and driver date |
| Sound | Devices, manufacturer, status, default output |
| Motherboard | Manufacturer, model, revision |
| BIOS | Vendor, version, date, boot mode |
| Disks | Model, capacity, bus type, media type, SMART health, serial |
| Partitions | Volume, file system, capacity, used, free, usage rate |
| Network | Adapters, MAC, IPv4/IPv6, link speed, status, traffic counters |
| Wi-Fi | SSID, BSSID, band, channel, signal, security, known networks |
| Displays | Resolution, size, refresh rate, aspect ratio, position |
| Battery | Charge, AC power, health, cycles, voltage, design and full capacity |
| Temperatures | ACPI zones, hardware sensors, disk temperature |
| System load | CPU load, memory load, processes, threads, uptime |

Plus a deep scan that adds RAM modules, GPU VRAM details and USB devices.

The interface is a sidebar of sections next to a card grid, with a live search
field that filters on label and value at once, accent-colored section icons, and
a bilingual UI (French and English) that switches instantly without recollecting.

## Requirements

Windows 10 or 11, Python 3.10 or newer when running from source.

| Component | x64 | ARM64 |
|---|---|---|
| Python source | Yes | Yes |
| `dist\check-conf.exe` | Yes | No |

The published executable is a **64-bit Intel build only**, because PyInstaller's
Windows bootloader that this project embeds is `Windows-64bit-intel`. On an
ARM64 machine (Snapdragon, etc.) the `.exe` will not run.

To get an ARM64 build, run the source directly on that machine, or rebuild there
with a matching ARM64 Python: PyInstaller emits a build for the interpreter it
runs on, so `build_exe.py` produces an ARM64 `.exe` when executed from an ARM64
Python. Nothing in the code is architecture-specific — collection relies on WMI
and PowerShell, both of which behave the same on either architecture.

Note that the app reports the *host* architecture in the System section, reading
`OSArchitecture` from WMI, so an ARM64 run still correctly shows the host value
and never assumes 64-bit Intel.

## Install

```
git clone https://github.com/your-account/check-conf.git
cd check-conf
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build the executable

```
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe build_exe.py
```

Produces a single self-contained `dist\check-conf.exe`, roughly 38 MB, with no
runtime dependency. The `.ico` is rendered from the same `app_pixmap()` code the
window uses, so the taskbar icon and the app icon never drift apart.

## Exports

| Format | Use |
|---|---|
| `.txt` | Paste into a support ticket or forum post |
| `.json` | Feed into a script or a support system |
| `.html` | Self-contained page, dark theme, with a print stylesheet |

Export from the toolbar (`Ctrl+E`) or copy the whole report to the clipboard
with `Ctrl+C`. Choosing the extension picks the format, anything else falls back
to text.

## How it collects

One batched PowerShell call fills a cached snapshot dict, then each collector
reads from that snapshot instead of spawning its own process. WMI is queried
through `Get-CimInstance`, the registry through `Get-ItemProperty`, disks
through `MSFT_Disk`, network counters through `Get-NetAdapterStatistics`.

Sections that are unavailable on a given machine are simply skipped instead of
failing the run. A section that does fail keeps its traceback tail visible in the
card, so a partial report is still useful.

Measured values keep their raw number next to the formatted string, which is
what lets the same report render as `1,91 GHz` in French and `1.91 GHz` in
English without collecting twice.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `F5` | Recollect |
| `Ctrl+E` | Export |
| `Ctrl+C` | Copy report |
| `Ctrl+Q` | Quit |

## Project layout

```
main.py                     entry point, language detection
pcinfo/
  ui.py                     main window, cards, search, export actions
  model.py                  Report / Section / Field
  theme.py                  colors and the Qt stylesheet
  icons.py                  SVG section icons, app icon
  i18n.py                   every user-facing string, French first
  export.py                 txt / json / html writers
  utils.py                  process, parsing, formatting helpers
  collectors/
    __init__.py             section registry, error isolation
    win.py                  the batched PowerShell snapshot
    windows.py              one collector per section
build_exe.py                PyInstaller wrapper
```

Adding a section means writing one collector function returning a `Section`,
registering it in `SPECS`, and adding its labels to `i18n.py`.

## Notes

Wi-Fi details need location services enabled on Windows 11, otherwise the
section reports that access was denied rather than showing stale data.

Temperatures come from ACPI zones and, when present, from
OpenHardwareMonitor or LibreHardwareMonitor.

## License

MIT
