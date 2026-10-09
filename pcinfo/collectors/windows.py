"""Windows collectors.

Every function reads the batched snapshot from :mod:`pcinfo.collectors.win`, so a
collection pass costs a single PowerShell round trip. Values are stored raw; the
label and the unit are resolved at display time from ``report.lang``.
"""

from __future__ import annotations

import math
import os
import platform

from ..i18n import t
from ..model import LEVEL_BAD, LEVEL_INFO, LEVEL_WARN, Report, Section
from ..utils import human_datetime
from . import win
from .base import add_bool, add_sentence, add_typed, kilobytes, megabytes_to_bytes, rate, reading

_STATUS_INFO = {
    1: "Other",
    2: "Unknown",
    3: "OK",
    4: "Degraded",
    5: "Minor",
    6: "Major",
    7: "Critical",
    8: "Non-recoverable",
    9: "Non-functional",
    10: "Disconnected",
    11: "Not present",
}

_USB_KINDS = {
    "USB": "kind.hub",
    "HIDClass": "kind.hid",
    "Audio": "kind.audio",
    "MEDIA": "kind.audio",
    "DiskDrive": "kind.storage",
    "USBSTOR": "kind.storage",
    "Printer": "kind.printer",
    "Net": "kind.network",
    "WSDP": "kind.portable",
    "SDHost": "kind.card",
    "SDMassStorage": "kind.card",
    "Composite": "kind.composite",
    "Image": "kind.scanner",
    "Camera": "kind.camera",
    "Bluetooth": "kind.bluetooth",
}


def _section(key: str) -> Section:
    return Section(key, key)


def system(report: Report, deep: bool) -> Section:
    sec = _section("system")
    os_info = win.first("Win32_OperatingSystem")
    reg_os = win.first("regOs")
    machine = win.first("Win32_ComputerSystem")
    product = win.first("Win32_ComputerSystemProduct")
    tz = win.SNAPSHOT.get("tz") or {}
    lang = report.lang

    report.hostname = os.environ.get("COMPUTERNAME") or platform.node()
    report.os_label = win.text(os_info.get("Caption")) or win.text(reg_os.get("ProductName"))
    reg_bios = win.first("regBios")
    sec.group("grp.identity")
    sec.add("pc.manu", win.text(product.get("Vendor")) or win.text(machine.get("Manufacturer")))
    sec.add("pc.brand", win.text(product.get("Name")) or win.text(machine.get("Model")))
    sec.add("pc.version", win.text(product.get("Version")) or win.text(machine.get("SystemFamily")))
    sec.add("pc.ref", win.text(reg_bios.get("SystemSKU")) or win.text(product.get("IdentifyingNumber")))
    sec.add("hostname", report.hostname)
    sec.group("grp.os")
    sec.add("os", report.os_label)
    sec.add("os.version", os_info.get("Version"))
    sec.add("os.build", f"{win.text(os_info.get('BuildNumber'))}.{win.text(reg_os.get('UBR'))}".strip("."))
    sec.add("os.arch", os_info.get("OSArchitecture"))
    sec.add("kernel", f"{win.text(os_info.get('Version'))}.{win.text(reg_os.get('UBR'))}".strip("."))
    sec.add(
        "edition",
        " - ".join(part for part in (win.text(reg_os.get("EditionID")), win.text(reg_os.get("DisplayVersion"))) if part),
    )
    installed = win.datetime_value(os_info.get("InstallDate"))
    if installed:
        sec.add("install", human_datetime(installed, lang))
    sec.group("grp.session")
    sec.add("user", os.environ.get("USERNAME") or os.environ.get("USER"))
    sec.add("shell", os.path.basename(os.environ.get("COMSPEC", "")) or None)
    add_typed(sec, "uptime", win.uptime() or None, "duration")
    boot = win.last_boot()
    if boot:
        sec.add("boot", human_datetime(boot, lang))
    sec.add("locale", " / ".join(part for part in (win.text(win.SNAPSHOT.get("culture")), win.text(win.SNAPSHOT.get("cultureSys"))) if part))
    if isinstance(tz, dict) and tz.get("Id"):
        offset = win.text(tz.get("Offset"))
        sec.add("tz", f"{tz['Id']} ({offset})" if offset else win.text(tz.get("Id")))
    hypervisor = machine.get("HypervisorPresent")
    if hypervisor is not None:
        sec.add("virt", t("value.yes" if hypervisor else "value.no", lang))
    model_name = win.text(machine.get("Model"))
    if "virtual" in model_name.casefold() or "vmware" in model_name.casefold():
        sec.add("virt", f"{t('value.yes', lang)} - {model_name}")
    return sec


def cpu(report: Report, deep: bool) -> Section:
    sec = _section("cpu")
    cores = win.rows("Win32_Processor")
    if not cores:
        return sec
    per_core = win.rows("Win32_PerfFormattedData_Counters_ProcessorInformation")
    total_load = [
        win.number(row.get("PercentProcessorPerformance")) or 0.0
        for row in per_core
        if win.text(row.get("Name")).endswith(",0")
    ]

    for index, row in enumerate(cores):
        name = win.text(row.get("Name")) or win.text(win.first("regCpu").get("ProcessorNameString"))
        if index == 0:
            sec.group("grp.cpu.chip")
            sec.add("cpu.name", name)
            add_typed(sec, "cpu.cores", row.get("NumberOfCores"), "int")
            add_typed(sec, "cpu.logical", row.get("NumberOfLogicalProcessors"), "int")
            add_typed(sec, "cpu.sockets", len(cores), "int")
            sec.group("grp.cpu.clock")
            add_typed(sec, "cpu.base", megahertz(row.get("CurrentClockSpeed")), "hz")
            add_typed(sec, "cpu.max", megahertz(row.get("MaxClockSpeed")), "hz")
            l2 = kilobytes(row.get("L2CacheSize"))
            l3 = kilobytes(row.get("L3CacheSize"))
            add_typed(sec, "cpu.l2", l2, "bytes")
            add_typed(sec, "cpu.l3", l3, "bytes")
            if l2 and l3:
                add_typed(sec, "cpu.cache", l2 + l3, "bytes")
            sec.group("grp.cpu.features")
            add_bool(sec, "cpu.virt", row.get("VirtualizationFirmwareEnabled"))
            add_bool(sec, "cpu.smt", row.get("SecondLevelAddressTranslationExtensions"))
            sec.group("grp.cpu.load")
            usage = win.number(row.get("LoadPercentage"))
            if usage is None and total_load:
                usage = round(sum(total_load) / len(total_load), 1)
            add_typed(sec, "cpu.usage", usage, "percent")
        else:
            sec.group("grp.cpu.chip")
            sec.add("cpu.name", name)
    if len(total_load) > 1:
        sec.group("grp.cpu.load")
        sec.add("cpu.percore", " / ".join(str(int(value)) for value in total_load))
    return sec


def megahertz(value):
    got = win.number(value)
    return got * 1_000_000.0 if got else None


def memory(report: Report, deep: bool) -> Section:
    sec = _section("memory")
    os_info = win.first("Win32_OperatingSystem")
    machine = win.first("Win32_ComputerSystem")
    array = win.first("Win32_PhysicalMemoryArray")
    modules = win.rows("physmem")

    installed = sum(win.number(row.get("Capacity")) or 0.0 for row in modules) if modules else 0.0
    if not installed:
        installed = kilobytes(array.get("MaxCapacity")) or kilobytes(machine.get("TotalPhysicalMemory")) or 0.0
    usable = kilobytes(os_info.get("TotalVisibleMemorySize")) or 0.0
    available = kilobytes(os_info.get("FreePhysicalMemory")) or 0.0
    used = max(0.0, usable - available)

    sec.group("grp.mem.main")
    add_typed(sec, "mem.total", installed, "bytes")
    add_typed(sec, "mem.used", used, "bytes")
    add_typed(sec, "mem.avail", available, "bytes")
    add_typed(sec, "mem.percent", win.safe_percent(used, usable), "percent")
    add_typed(sec, "mem.slots", array.get("MemoryDevices"), "int")
    add_typed(sec, "mem.usedslots", len(modules) if modules else None, "int")

    if deep and modules:
        for index, module in enumerate(modules):
            part = win.text(module.get("PartNumber"))
            vendor = win.text(module.get("Manufacturer"))
            sec.group(part or vendor or f"{t('grp.mem.module', report.lang)} {index + 1}")
            sec.add("mem.module", part or vendor or t("value.unknown", report.lang))
            sec.add("mem.slot", win.text(module.get("DeviceLocator")) or win.text(module.get("BankLabel")))
            add_typed(sec, "mem.cap", win.number(module.get("Capacity")), "bytes")
            sec.add("mem.type", win.MEMORY_TYPES.get(win.integer(module.get("SMBIOSMemoryType"), -1), ""))
            add_typed(sec, "mem.speed", megahertz(module.get("Speed") or module.get("ConfiguredClockSpeed")), "hz")
            sec.add("mem.vendor", vendor)
            sec.add("mem.partno", part)
            sec.add("mem.serial", win.text(module.get("SerialNumber")))

    swap_total = sum(megabytes_to_bytes(row.get("AllocatedBaseSize")) or 0.0 for row in win.rows("Win32_PageFileUsage"))
    swap_used = sum(megabytes_to_bytes(row.get("CurrentUsage")) or 0.0 for row in win.rows("Win32_PageFileUsage"))
    if swap_total:
        sec.group("grp.mem.swap")
        add_typed(sec, "swap.total", swap_total, "bytes")
        add_typed(sec, "swap.used", swap_used, "bytes")
        sec.group()
    return sec


def gpu(report: Report, deep: bool) -> Section:
    sec = _section("gpu")
    controllers = win.rows("Win32_VideoController")
    add_typed(sec, "gpu.count", len(controllers) or None, "int")
    for row in controllers:
        sec.group(win.text(row.get("Name")) or t("value.unknown", report.lang))
        sec.add("gpu.name", win.text(row.get("Name")))
        sec.add("gpu.vendor", win.text(row.get("AdapterCompatibility")))
        add_typed(sec, "gpu.vram", win.number(row.get("AdapterRAM")), "bytes")
        sec.add("gpu.driver", win.text(row.get("DriverVersion")))
        driver_date = win.datetime_value(row.get("DriverDate"))
        if driver_date:
            sec.add("gpu.driverdate", human_datetime(driver_date, report.lang))
        sec.add("gpu.pci", win.pci_address(row.get("PNPDeviceID")))
        width = win.integer(row.get("CurrentHorizontalResolution"))
        height = win.integer(row.get("CurrentVerticalResolution"))
        if width and height:
            sec.add("gpu.res", f"{width}x{height}")
        add_typed(sec, "gpu.refresh", win.number(row.get("CurrentRefreshRate")), "hz")
        sec.add("gpu.api", win.text(row.get("VideoProcessor")))
    if not controllers:
        sec.add("gpu.name", t("value.absent", report.lang), level=LEVEL_WARN)
    return sec


def sound(report: Report, deep: bool) -> Section:
    sec = _section("sound")
    devices = win.rows("Win32_SoundDevice")
    add_typed(sec, "sound.count", len(devices) or None, "int")
    for row in devices:
        sec.group(win.text(row.get("Name")) or t("value.unknown", report.lang))
        sec.add("sound.name", win.text(row.get("Name")))
        sec.add("sound.vendor", win.text(row.get("Manufacturer")) or win.text(row.get("ProductName")))
        info = _STATUS_INFO.get(win.integer(row.get("StatusInfo"), -1), "")
        status = win.text(row.get("Status"))
        if info and info != status:
            status = f"{status} ({info})" if status else info
        sec.add("sound.status", status, level=LEVEL_WARN if win.text(row.get("Status")) not in ("OK", "") else LEVEL_INFO)
    if not devices:
        sec.add("sound.name", t("value.absent", report.lang), level=LEVEL_WARN)
    return sec


def board(report: Report, deep: bool) -> Section:
    sec = _section("board")
    base = win.first("Win32_BaseBoard")
    reg = win.first("regBios")
    sec.add("board.vendor", win.text(base.get("Manufacturer")) or win.text(reg.get("SystemManufacturer")))
    sec.add("board.model", win.text(base.get("Product")) or win.text(reg.get("BaseBoardProduct")))
    sec.add("board.version", win.text(base.get("Version")))
    return sec


def bios(report: Report, deep: bool) -> Section:
    sec = _section("bios")
    row = win.first("Win32_BIOS")
    reg = win.first("regBios")
    sec.add("bios.vendor", win.text(row.get("Manufacturer")) or win.text(reg.get("BIOSVendor")))
    sec.add("bios.version", win.text(row.get("SMBIOSBIOSVersion")) or win.text(reg.get("BIOSVersion")))
    released = win.datetime_value(row.get("ReleaseDate")) or win.datetime_value(reg.get("BIOSReleaseDate"))
    if released:
        sec.add("bios.date", human_datetime(released, report.lang))
    firmware = win.text(win.SNAPSHOT.get("firmware"))
    if firmware:
        sec.add("bios.mode", firmware)
    return sec


def disk(report: Report, deep: bool) -> Section:
    sec = _section("disk")
    drives = win.rows("Win32_DiskDrive")
    msft = {win.integer(row.get("Number"), -1): row for row in win.rows("msftDisk")}
    physical = {win.text(row.get("FriendlyName")): row for row in win.rows("msftPhysical")}
    add_typed(sec, "disk.count", len(drives) or None, "int")

    for index, row in enumerate(drives):
        model = win.text(row.get("Model"))
        extra = msft.get(index, {})
        media = physical.get(model, {})
        sec.group(model or f"{t('grp.disk.device', report.lang)} {index + 1}")
        sec.add("disk.model", model)
        add_typed(sec, "disk.size", win.number(row.get("Size")), "bytes")
        bus = win.BUS_TYPES.get(win.integer(extra.get("BusType"), -1), "")
        if not bus:
            bus = win.text(row.get("InterfaceType"))
        sec.add("disk.bus", bus)
        sec.add("disk.media", win.MEDIA_TYPES.get(win.integer(media.get("MediaType"), -1), ""))
        health = win.HEALTH_STATES.get(win.integer(extra.get("HealthStatus"), -1), "")
        level = LEVEL_INFO if health in ("", "Healthy") else LEVEL_BAD if health == "Unhealthy" else LEVEL_WARN
        if health:
            sec.add("disk.health", health, level=level)
        sec.add("disk.serial", win.text(row.get("SerialNumber")))
        sec.add("disk.firmware", win.text(row.get("FirmwareRevision")) or win.text(extra.get("FirmwareVersion")))
        add_typed(sec, "disk.partitions", row.get("Partitions"), "int")
    if not drives:
        sec.add("disk.model", t("value.absent", report.lang), level=LEVEL_WARN)
    return sec


def partitions(report: Report, deep: bool) -> Section:
    sec = _section("partitions")
    for row in win.rows("Win32_LogicalDisk"):
        if win.integer(row.get("DriveType"), 0) != 3:
            continue
        size = win.number(row.get("Size"))
        free = win.number(row.get("FreeSpace"))
        device = win.text(row.get("DeviceID"))
        volume = win.text(row.get("VolumeName"))
        sec.group(f"{device} — {volume}" if volume else device or t("value.unknown", report.lang))
        sec.add("part.label", device)
        sec.add("part.fs", win.text(row.get("FileSystem")))
        add_typed(sec, "part.size", size, "bytes")
        add_typed(sec, "part.free", free, "bytes")
        add_typed(sec, "part.used", (size - free) if size is not None and free is not None else None, "bytes")
        add_typed(sec, "part.percent", win.safe_percent((size or 0) - (free or 0), size), "percent")
        sec.add("part.type", win.text(row.get("Description")))
    return sec


def _by_interface(rows) -> dict:
    grouped: dict = {}
    for row in rows:
        grouped.setdefault(win.integer(row.get("InterfaceIndex"), -1), []).append(row)
    return grouped


def network(report: Report, deep: bool) -> Section:
    sec = _section("network")
    adapters = win.rows("netAdapter")
    addresses = _by_interface(win.rows("netAddr"))
    dns = _by_interface(win.rows("netDns"))
    routes = {win.integer(row.get("InterfaceIndex"), -1): win.text(row.get("NextHop")) for row in win.rows("netRoute")}
    stats = {win.text(row.get("Name")): row for row in win.rows("netStats")}
    lang = report.lang
    add_typed(sec, "net.count", len(adapters) or None, "int")
    adapters.sort(key=lambda row: (win.text(row.get("Status")) != "Up", win.is_virtual(row)))

    for row in adapters:
        name = win.text(row.get("Name"))
        index = win.integer(row.get("ifIndex"), -1)
        sec.group(name or win.text(row.get("InterfaceDescription")) or t("value.unknown", lang))
        sec.add("net.adapter", name or win.text(row.get("InterfaceDescription")))
        sec.add("net.type", win.NET_IF_TYPES.get(win.integer(row.get("InterfaceType"), -1)) or win.text(row.get("InterfaceDescription")) or t("value.unknown", lang))
        sec.add("net.mac", win.mac(row.get("MacAddress")))
        v4, v6 = [], []
        for entry in addresses.get(index, []):
            (v4 if win.integer(entry.get("AddressFamily"), 0) == 2 else v6).append(win.text(entry.get("IPAddress")))
        sec.add("net.ipv4", ", ".join(v4))
        sec.add("net.ipv6", ", ".join(v6))
        status = win.text(row.get("Status"))
        sec.add("net.status", status, level=LEVEL_INFO if status == "Up" else LEVEL_WARN)
        link = win.bit_rate(row.get("LinkSpeed"))
        if link:
            sec.add("net.speed", rate(link, lang))
        sec.add("net.gateway", routes.get(index))
        servers = []
        for entry in dns.get(index, []):
            raw_servers = entry.get("ServerAddresses")
            if isinstance(raw_servers, list):
                servers.extend(win.text(part) for part in raw_servers)
            elif raw_servers:
                servers.append(win.text(raw_servers))
        sec.add("net.dns", ", ".join(part for part in servers if part))
        if deep:
            counter = stats.get(name, {})
            add_typed(sec, "net.rx", win.number(counter.get("ReceivedBytes")), "bytes")
            add_typed(sec, "net.tx", win.number(counter.get("SentBytes")), "bytes")
    if not adapters:
        sec.add("net.adapter", t("value.absent", report.lang), level=LEVEL_WARN)
    return sec


def wifi(report: Report, deep: bool) -> Section:
    sec = _section("wifi")
    lang = report.lang
    interfaces = win.wlan_interfaces()
    if not interfaces:
        raw = win.text(win.SNAPSHOT.get("wlanIface"))
        if "refus" in raw.casefold() or "denied" in raw.casefold():
            sec.add("wifi.status", t("wifi.denied", lang), level=LEVEL_WARN)
        else:
            sec.add("wifi.status", t("value.absent", lang), level=LEVEL_WARN)
        if deep:
            add_typed(sec, "wifi.known", win.known_profiles() or None, "int")
        return sec

    for entry in interfaces:
        sec.group(entry.get("ssid") or t("value.unknown", lang))
        sec.add("wifi.ssid", entry.get("ssid"))
        sec.add("wifi.bssid", win.mac(entry.get("bssid")))
        sec.add("wifi.adapter", entry.get("description"))
        sec.add("wifi.band", entry.get("radio"))
        sec.add("wifi.channel", entry.get("channel"))
        signal = win.number((entry.get("signal") or "").rstrip("% "))
        add_typed(sec, "wifi.signal", signal, "percent")
        link = max(win.number(entry.get("rx")) or 0.0, win.number(entry.get("tx")) or 0.0)
        if link:
            sec.add("wifi.speed", rate(link * 1_000_000, lang))
        sec.add("wifi.security", entry.get("auth"))
        state = win.text(entry.get("state"))
        sec.add("wifi.status", state, level=LEVEL_INFO if state.casefold() == "connected" else LEVEL_WARN)
    if deep:
        sec.group("grp.wifi.known")
        add_typed(sec, "wifi.known", win.known_profiles() or None, "int")
    return sec


def display(report: Report, deep: bool) -> Section:
    sec = _section("display")
    lang = report.lang
    monitors = win.rows("WmiMonitorID")
    sizes = {win.text(row.get("InstanceName")): row for row in win.rows("WmiMonitorBasicDisplayParams")}
    outputs = {win.text(row.get("InstanceName")): row for row in win.rows("WmiMonitorConnectionParams")}
    controllers = win.rows("Win32_VideoController")
    modes = win.rows("monModes")

    for index, monitor in enumerate(monitors):
        instance = win.text(monitor.get("InstanceName"))
        name = win.wmi_chars(monitor.get("UserFriendlyName"))
        if not name:
            name = " ".join(
                part
                for part in (win.wmi_chars(monitor.get("ManufacturerName")), win.wmi_chars(monitor.get("ProductCodeID")))
                if part
            )
        sec.group(name or t("value.unknown", lang))
        sec.add("disp.name", name or t("value.unknown", lang))

        best = None
        for mode in modes:
            if win.text(mode.get("InstanceName")) != instance:
                continue
            width = win.integer(mode.get("W"))
            height = win.integer(mode.get("H"))
            hertz = win.number(mode.get("HzNum")) / (win.number(mode.get("HzDen")) or 1.0)
            candidate = (width * height, width, height, hertz)
            if best is None or candidate[0] > best[0]:
                best = candidate
        if best:
            _, width, height, hertz = best
            sec.add("disp.res", f"{width}x{height}")
            add_typed(sec, "disp.refresh", hertz, "hz")
            if width and height:
                ratio = _ratio(width, height)
                if ratio:
                    sec.add("disp.ratio", ratio)

        size_row = sizes.get(instance, {})
        diagonal = _diagonal(size_row, lang)
        if diagonal:
            sec.add("disp.size", diagonal)

        if index == 0:
            add_bool(sec, "disp.primary", monitor.get("Active"))
        output = win.video_output((outputs.get(instance) or {}).get("VideoOutputTechnology"))
        if output:
            sec.add("disp.pos", output)

    if not monitors and controllers:
        for row in controllers:
            width = win.integer(row.get("CurrentHorizontalResolution"))
            height = win.integer(row.get("CurrentVerticalResolution"))
            if width and height:
                sec.add("disp.name", win.text(row.get("Name")))
                sec.add("disp.res", f"{width}x{height}")
    return sec


def _ratio(width: int, height: int) -> str:
    if not width or not height:
        return ""
    divisor = math.gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


def _diagonal(row: dict, lang: str = "fr") -> str:
    from ..utils import num

    width = win.number(row.get("MaxHorizontalImageSize"))
    height = win.number(row.get("MaxVerticalImageSize"))
    if not width or not height:
        return ""
    inches = ((width**2 + height**2) ** 0.5) / 2.54
    return f'{num(inches, 1, lang)}"'


_MWH_MIN = 0.0
_MWH_MAX = 1e7


def _mwh(value):
    """WMI reports energy in mWh; some drivers publish garbage like 0xFFFFFFFF."""
    got = win.number(value)
    if got is None or not _MWH_MIN < got <= _MWH_MAX:
        return None
    return got


def _sum_mwh(rows_, field):
    total = sum(_mwh(row.get(field)) or 0.0 for row in rows_)
    return total or None


def _mah(mwh, millivolts):
    """Charge in mAh is the mWh the pack holds divided by its voltage."""
    if not mwh or not millivolts or millivolts <= 0:
        return None
    return mwh * 1000.0 / millivolts


def _mean_voltage(packs, status_rows):
    """Averages the pack voltages so a summed mWh figure stays meaningful."""
    volts = [win.number(row.get("DesignVoltage")) for row in packs]
    volts = [v for v in volts if v and v > 0]
    if not volts:
        volts = [win.number(row.get("Voltage")) for row in status_rows]
        volts = [v for v in volts if v and v > 0]
    return sum(volts) / len(volts) if volts else None


def battery(report: Report, deep: bool) -> Section:
    sec = _section("battery")
    lang = report.lang
    packs = win.rows("Win32_Battery")
    status_rows = win.rows("batStatus")
    add_typed(sec, "batt.count", len(packs), "int")
    full = _sum_mwh(win.rows("batFull"), "FullChargedCapacity") or _sum_mwh(packs, "FullChargeCapacity")
    design = _sum_mwh(win.rows("batStatic"), "DesignedCapacity") or _sum_mwh(packs, "DesignCapacity")
    cycles = sum(win.integer(row.get("CycleCount")) for row in win.rows("batCycle"))

    for row in packs:
        sec.group(win.text(row.get("Name")) or t("value.unknown", lang))
        sec.add("batt.name", win.text(row.get("Name")))
        add_typed(sec, "batt.level", win.number(row.get("EstimatedChargeRemaining")), "percent")
        status = win.integer(row.get("BatteryStatus"), -1)
        add_bool(sec, "batt.plugged", None if status < 0 else status == 2)
        runtime = win.number(row.get("EstimatedRunTime"))
        if runtime and runtime < 172_800:
            add_typed(sec, "batt.runtime", runtime * 60.0, "duration")
        voltage = win.number(row.get("DesignVoltage"))
        if voltage:
            add_typed(sec, "batt.voltage", voltage / 1000.0, "volt")
        chemistry = win.CHEMISTRY.get(win.integer(row.get("Chemistry"), -1), "")
        if chemistry and chemistry != "Unknown":
            sec.add("batt.tech", chemistry)

    millivolts = _mean_voltage(packs, status_rows)
    if full or design:
        sec.group("grp.batt.capacity")
    if full:
        add_typed(sec, "batt.energy", full / 1000.0, "wh")
        add_typed(sec, "batt.full", _mah(full, millivolts) or full / 1000.0, "mah")
    if design:
        add_typed(sec, "batt.design", _mah(design, millivolts) or design / 1000.0, "mah")
    if design and full:
        add_typed(sec, "batt.health", win.safe_percent(full, design), "percent")
    if deep and cycles:
        add_typed(sec, "batt.cycles", cycles, "int")
    if not packs:
        sec.add("batt.name", t("value.absent", lang), level=LEVEL_WARN)
    return sec


def temp(report: Report, deep: bool) -> Section:
    sec = _section("temp")
    sensors = []

    for row in win.rows("MSAcpi_ThermalZoneTemperature"):
        if win.text(row.get("Active")).casefold() == "false":
            continue
        zone = win.text(row.get("InstanceName")).split("\\")[-1] or "ACPI"
        current = win.celsius(row.get("CurrentTemperature"))
        if current is None:
            continue
        sensors.append(("f.temp.acpi", zone, "", current, win.celsius(row.get("CriticalTripPoint"))))

    for row in win.rows("hwTemp"):
        label = win.text(row.get("Name"))
        value = win.number(row.get("Value"))
        if label and value is not None:
            sensors.append(("f.temp.hw", label, "", value, None))

    if deep:
        disks = {win.integer(row.get("Number"), -1): row for row in win.rows("msftDisk")}
        physical = {win.text(row.get("FriendlyName")): row for row in win.rows("msftPhysical")}
        for row in win.rows("diskRel"):
            temperature = win.number(row.get("Temperature"))
            if temperature is None:
                continue
            disk = disks.get(win.integer(row.get("DeviceId"), -1), {})
            name = win.text(disk.get("FriendlyName"))
            media = physical.get(name, {})
            detail = " / ".join(
                part
                for part in (
                    win.DISK_MEDIA.get(win.integer(media.get("MediaType"), -1)),
                    win.DISK_BUS.get(win.integer(disk.get("BusType"), -1)),
                )
                if part
            )
            sensors.append(("f.temp.disk", name, detail, temperature, None))

    for prefix, name, detail, value, critical in sensors:
        def render(lang: str, prefix=prefix, name=name, detail=detail, value=value, critical=critical) -> str:
            label = f"{t(prefix, lang)} {name}".strip()
            if detail:
                label = f"{label} ({detail})"
            text = f"{label} : {reading('temp', value, lang)}"
            if critical is not None:
                text += f" ({t('f.temp.critical_at', lang)} {reading('temp', critical, lang)})"
            return text

        sec.group(f"{name} ({detail})" if detail else name)
        add_sentence(sec, "temp.name", render)

    if not sensors:
        sec.add("temp.name", t("value.absent", report.lang), level=LEVEL_WARN)
    return sec


def usb(report: Report, deep: bool) -> Section:
    sec = _section("usb")
    lang = report.lang
    devices = win.rows("usbDetail")
    add_typed(sec, "usb.count", len(devices) or None, "int")
    for row in devices:
        sec.group(win.text(row.get("Name")) or t("value.unknown", lang))
        sec.add("usb.name", win.text(row.get("Name")))
        sec.add("usb.vendor", win.text(row.get("Manufacturer")))
        cls = win.text(row.get("PNPClass"))
        sec.add("usb.type", t(_USB_KINDS.get(cls, "value.unknown"), lang) if cls else t("value.unknown", lang))
    if not devices:
        sec.add("usb.name", t("value.absent", report.lang), level=LEVEL_WARN)
    return sec


def load(report: Report, deep: bool) -> Section:
    sec = _section("load")
    os_info = win.first("Win32_OperatingSystem")
    perf = win.first("Win32_PerfFormattedData_PerfOS_System")
    processors = win.rows("Win32_Processor")
    lang = report.lang

    usage = win.number((processors[0] if processors else {}).get("LoadPercentage"))
    if usage is None:
        values = [
            win.number(row.get("PercentProcessorPerformance"))
            for row in win.rows("Win32_PerfFormattedData_Counters_ProcessorInformation")
            if win.text(row.get("Name")).endswith(",0")
        ]
        values = [value for value in values if value is not None]
        usage = round(sum(values) / len(values), 1) if values else None
    add_typed(sec, "load.cpu", usage, "percent")

    usable = kilobytes(os_info.get("TotalVisibleMemorySize")) or 0.0
    available = kilobytes(os_info.get("FreePhysicalMemory")) or 0.0
    add_typed(sec, "load.ram", win.safe_percent(usable - available, usable), "percent")
    add_typed(sec, "load.procs", win.number(os_info.get("NumberOfProcesses")) or perf.get("Processes"), "int")
    add_typed(sec, "load.threads", perf.get("Threads"), "int")
    add_typed(sec, "load.uptime", win.uptime() or None, "duration")
    boot = win.last_boot()
    if boot:
        sec.add("load.boot", human_datetime(boot, lang))
    return sec
