"""Windows data layer.

A single batched PowerShell call fills a plain dict; every collector then reads
that snapshot instead of spawning its own process. The snapshot is cached for the
duration of one collection pass.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from ..utils import IS_WINDOWS, powershell

SNAPSHOT: dict = {}
SNAPSHOT_KEY: tuple | None = None

_ACPI_OFFSET = 273.15
_DATE_RE = re.compile(r"^/Date\((-?\d+)")
_PAIR_RE = re.compile(r"^\s{2,}([^:]+?)\s*:\s*(.*)$")

BUS_TYPES = {
    0: "Unknown",
    1: "SCSI",
    2: "ATAPI",
    3: "ATA",
    4: "IEEE 1394",
    5: "SSA",
    6: "Fibre Channel",
    7: "USB",
    8: "RAID",
    9: "iSCSI",
    10: "SAS",
    11: "SATA",
    12: "SD",
    13: "MMC",
    14: "Virtual",
    15: "File-backed virtual",
    16: "Storage Spaces",
    17: "NVMe",
    18: "SCM",
    19: "UFS",
}

MEDIA_TYPES = {0: "Unknown", 3: "HDD", 4: "SSD", 5: "SCM"}

HEALTH_STATES = {0: "Healthy", 1: "Warning", 2: "Unhealthy", 5: "Unknown"}

MEMORY_TYPES = {
    20: "DDR",
    21: "DDR2",
    22: "DDR2 FB-DIMM",
    24: "DDR3",
    26: "DDR4",
    34: "DDR5",
    35: "LPDDR4",
    36: "LPDDR5",
    37: "LPDDR5X",
}

FORM_FACTORS = {3: "DIMM", 4: "SODIMM", 8: "SODIMM", 9: "SRIMM", 12: "SODIMM", 13: "SRIMM"}

NET_IF_TYPES = {
    0: "Unknown",
    1: "Other",
    6: "Ethernet",
    18: "Multipoint",
    23: "PPP",
    24: "Loopback",
    37: "ATM",
    51: "Tunnel",
    53: "PPPoE",
    71: "Wi-Fi",
    94: "ISDN",
    131: "Tunnel",
    135: "Wi-Fi",
    136: "NDIS",
    161: "WWAN",
    163: "WWAN",
    237: "Authentication",
    243: "Media redirection",
}

DISK_BUS = {
    0: "Unknown",
    1: "SCSI",
    2: "ATAPI",
    3: "ATA",
    4: "1394",
    5: "SSA",
    6: "Fibre",
    7: "USB",
    8: "RAID",
    9: "iSCSI",
    10: "SAS",
    11: "SATA",
    12: "SD",
    13: "MMC",
    14: "Virtual",
    15: "File-backed virtual",
    16: "Storage Spaces",
    17: "NVMe",
}

DISK_MEDIA = {0: "Unspecified", 3: "HDD", 4: "SSD", 5: "SCM"}

SLOT_LABELS = {0: "Other", 1: "Unknown", 2: "Processor", 3: "Mezzanine", 4: "Card", 6: "Module"}

CHEMISTRY = {
    1: "Other",
    2: "Unknown",
    3: "Lead acid",
    4: "NiCd",
    5: "NiMH",
    6: "Li-ion",
    7: "Zinc air",
    8: "Li-poly",
}

VIDEO_OUTPUT = {
    0: "VGA",
    2: "S-Video",
    3: "Composite",
    4: "Component",
    5: "Composite",
    6: "DVI",
    8: "DVI",
    9: "DVI",
    10: "Component",
    11: "DisplayPort",
    12: "HDMI",
    13: "LVDS",
    14: "Miracast",
    15: "Indirect",
    16: "Internal",
    17: "UDI",
    18: "SDI",
    19: "Miracast",
    20: "IndirectWired",
    21: "IndirectVirtual",
    2147483648: "Internal",
}

# netsh localizes its labels, so both spellings are accepted.
WLAN_ALIASES = {
    "ssid": ("name", "nom", "ssid"),
    "description": ("description",),
    "guid": ("guid",),
    "bssid": ("physical address", "adresse physique", "bssid"),
    "state": ("state", "état", "etat"),
    "network": ("network type", "type de réseau", "network"),
    "radio": ("radio type", "type radio"),
    "auth": ("authentication", "authentification"),
    "channel": ("channel", "canal"),
    "signal": ("signal", "force du signal"),
    "rx": ("receive rate (mbps)", "débit de réception"),
    "tx": ("transmit rate (mbps)", "débit de transmission"),
    "profile": ("profile", "profil"),
}



def _script(deep: bool) -> str:
    deep_block = (
        r"""
$o['physmem'] = @(Get-CimInstance Win32_PhysicalMemory -ErrorAction SilentlyContinue | Select-Object DeviceLocator, BankLabel, Capacity, Speed, ConfiguredClockSpeed, Manufacturer, PartNumber, SerialNumber, FormFactor, SMBIOSMemoryType, MemoryType)
$o['monModes'] = @(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorListedSupportedSourceModes | ForEach-Object { $inst = $_.InstanceName; $_.MonitorSourceModes | ForEach-Object { $m = $_; [pscustomobject]@{ InstanceName=$inst; W=$m.HorizontalActivePixels; H=$m.VerticalActivePixels; HzNum=$m.VerticalRefreshRateNumerator; HzDen=$m.VerticalRefreshRateDenominator; Interlaced=$m.InterlaceMode } } })
$o['batStatic'] = @(Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData | Select-Object InstanceName, DesignedCapacity)
$o['batCycle'] = @(Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount | Select-Object InstanceName, CycleCount)
$o['diskRel'] = @(Get-PhysicalDisk -ErrorAction SilentlyContinue | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | Select-Object DeviceId, Temperature, Wear, PowerOnHours, ReadErrorsTotal, WriteErrorsTotal)
$o['netStats'] = @(Get-NetAdapterStatistics | Select-Object Name, ReceivedBytes, SentBytes, ReceivedPackets, SentPackets)
$o['wlanProfiles'] = (netsh wlan show profiles) -join "`n"
$o['hwTemp'] = @(foreach ($ns in @('root/OpenHardwareMonitor','root/LibreHardwareMonitor')) { try { Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction Stop | Where-Object { $_.SensorType -eq 'Temperature' } | Select-Object Name, Value, Identifier } catch { } })
$o['usbDetail'] = @(Get-CimInstance Win32_PnPEntity -Filter "PNPDeviceID LIKE 'USB%'" -ErrorAction SilentlyContinue | Select-Object Name, Manufacturer, Service, DeviceID, Status, PNPClass)
"""
        if deep
        else ""
    )
    return (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        "$ProgressPreference = 'SilentlyContinue'\n"
        "$o = [ordered]@{}\n"
        "$sel = { param($n, $p, $ns) $c = Get-CimInstance -ClassName $n -Namespace $ns -ErrorAction SilentlyContinue | Select-Object -Property $p; $o[$n] = @($c) }\n"
        "& $sel 'Win32_OperatingSystem' @('Caption','Version','BuildNumber','OSArchitecture','InstallDate','LastBootUpTime','Locale','MUILanguages','TotalVisibleMemorySize','FreePhysicalMemory','TotalVirtualMemorySize','FreeVirtualMemory') 'root/cimv2'\n"
        "& $sel 'Win32_ComputerSystem' @('Manufacturer','Model','SystemType','TotalPhysicalMemory','HypervisorPresent','NumberOfProcessors','NumberOfLogicalProcessors','PCSystemType','SystemFamily') 'root/cimv2'\n"
        "& $sel 'Win32_ComputerSystemProduct' @('Vendor','Name','Version','IdentifyingNumber','UUID') 'root/cimv2'\n"
        "& $sel 'Win32_Processor' @('Name','Manufacturer','NumberOfCores','NumberOfLogicalProcessors','MaxClockSpeed','CurrentClockSpeed','L2CacheSize','L3CacheSize','SocketDesignation','VirtualizationFirmwareEnabled','SecondLevelAddressTranslationExtensions','LoadPercentage','Architecture','AddressWidth') 'root/cimv2'\n"
        "& $sel 'Win32_PhysicalMemoryArray' @('MemoryDevices','MaxCapacity') 'root/cimv2'\n"
        "& $sel 'Win32_VideoController' @('Name','AdapterCompatibility','AdapterRAM','DriverVersion','DriverDate','PNPDeviceID','VideoProcessor','VideoModeDescription','CurrentHorizontalResolution','CurrentVerticalResolution','CurrentRefreshRate','CurrentBitsPerPixel','AdapterBusWidth','Status') 'root/cimv2'\n"
        "& $sel 'Win32_SoundDevice' @('Name','Manufacturer','ProductName','Status','StatusInfo','DeviceID') 'root/cimv2'\n"
        "& $sel 'Win32_BaseBoard' @('Manufacturer','Product','Version','Tag','SerialNumber') 'root/cimv2'\n"
        "& $sel 'Win32_BIOS' @('Manufacturer','SMBIOSBIOSVersion','ReleaseDate','SerialNumber','Version','Status') 'root/cimv2'\n"
        "& $sel 'Win32_DiskDrive' @('Model','Size','InterfaceType','MediaType','SerialNumber','FirmwareRevision','Index','Partitions','DeviceID','Status') 'root/cimv2'\n"
        "& $sel 'Win32_LogicalDisk' @('DeviceID','VolumeName','FileSystem','Size','FreeSpace','DriveType','VolumeSerialNumber','Description') 'root/cimv2'\n"
        "& $sel 'Win32_Battery' @('Name','DeviceID','EstimatedChargeRemaining','BatteryStatus','EstimatedRunTime','DesignVoltage','DesignCapacity','FullChargeCapacity','BatteryRechargeTime','Status','Chemistry') 'root/cimv2'\n"
        "$o['batFull'] = @(Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue | Select-Object InstanceName, FullChargedCapacity)\n"
        "$o['batStatus'] = @(Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object InstanceName, Voltage, RemainingCapacity)\n"
        "& $sel 'Win32_PageFileUsage' @('Name','AllocatedBaseSize','CurrentUsage','PeakUsage') 'root/cimv2'\n"
        "& $sel 'Win32_PerfFormattedData_PerfOS_System' @('Processes','Threads','SystemUpTime','ProcessorQueueLength') 'root/cimv2'\n"
        "& $sel 'Win32_PerfFormattedData_Counters_ProcessorInformation' @('Name','ProcessorFrequency','PercentProcessorPerformance') 'root/cimv2'\n"
        "& $sel 'WmiMonitorID' @('InstanceName','Active','ManufacturerName','ProductCodeID','SerialNumberID','UserFriendlyName') 'root/wmi'\n"
        "& $sel 'WmiMonitorBasicDisplayParams' @('InstanceName','MaxHorizontalImageSize','MaxVerticalImageSize','VideoInputType') 'root/wmi'\n"
        "& $sel 'WmiMonitorConnectionParams' @('InstanceName','VideoOutputTechnology') 'root/wmi'\n"
        "& $sel 'MSAcpi_ThermalZoneTemperature' @('InstanceName','CurrentTemperature','CriticalTripPoint','Active') 'root/wmi'\n"
        "$o['regBios'] = @((Get-ItemProperty 'HKLM:\\HARDWARE\\DESCRIPTION\\System\\BIOS' -ErrorAction SilentlyContinue) | Select-Object SystemManufacturer, SystemProductName, SystemFamily, BaseBoardManufacturer, BaseBoardProduct, BIOSVendor, BIOSVersion, BIOSReleaseDate, SystemSKU)\n"
        "$o['regOs'] = @((Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion' -ErrorAction SilentlyContinue) | Select-Object ProductName, DisplayVersion, EditionID, CurrentBuild, UBR, InstallationType)\n"
        "$o['regCpu'] = @((Get-ItemProperty 'HKLM:\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0' -ErrorAction SilentlyContinue) | Select-Object ProcessorNameString, Identifier, VendorIdentifier, '~MHz')\n"
        "$o['firmware'] = $env:firmware_type\n"
        "$o['culture'] = [System.Globalization.CultureInfo]::CurrentUICulture.Name\n"
        "$o['cultureSys'] = (Get-Culture).Name\n"
        "$o['tz'] = [ordered]@{ Id = [System.TimeZoneInfo]::Local.Id; Offset = [System.TimeZoneInfo]::Local.BaseUtcOffset.ToString() }\n"
        "$o['netAdapter'] = @(Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, MacAddress, LinkSpeed, MediaType, InterfaceType, ifIndex)\n"
        "$o['netAddr'] = @(Get-NetIPAddress -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike 'fe80:*' } | Select-Object InterfaceIndex, IPAddress, AddressFamily, PrefixLength)\n"
        "$o['netDns'] = @(Get-DnsClientServerAddress -ErrorAction SilentlyContinue | Select-Object InterfaceIndex, AddressFamily, ServerAddresses)\n"
        "$o['netRoute'] = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object InterfaceIndex, NextHop, RouteMetric)\n"
        "$o['wlanIface'] = (netsh wlan show interfaces) -join \"`n\"\n"
        "$o['msftDisk'] = @(Get-CimInstance -Namespace 'root/Microsoft/Windows/Storage' -ClassName MSFT_Disk -ErrorAction SilentlyContinue | Select-Object Number, FriendlyName, BusType, Size, HealthStatus, FirmwareVersion, SerialNumber)\n"
        "$o['msftPhysical'] = @(Get-CimInstance -Namespace 'root/Microsoft/Windows/Storage' -ClassName MSFT_PhysicalDisk -ErrorAction SilentlyContinue | Select-Object FriendlyName, BusType, MediaType, Size, HealthStatus)\n"
        + deep_block
        + "$o | ConvertTo-Json -Depth 7 -Compress\n"
    )


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _one(value) -> dict:
    rows = _as_list(value)
    return rows[0] if rows else {}


def snapshot(deep: bool = False, force: bool = False) -> dict:
    """Collect everything Windows knows, in one PowerShell round trip."""
    global SNAPSHOT, SNAPSHOT_KEY

    if not IS_WINDOWS:
        return {}
    key = (deep,)
    if not force and SNAPSHOT_KEY == key and SNAPSHOT:
        return SNAPSHOT
    raw = powershell(_script(deep), timeout=180)
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    SNAPSHOT = data
    SNAPSHOT_KEY = key
    return SNAPSHOT


def rows(key: str) -> list:
    return _as_list(SNAPSHOT.get(key))


def first(key: str) -> dict:
    return _one(SNAPSHOT.get(key))


def text(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def number(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value, default: int = 0) -> int:
    got = number(value)
    return int(got) if got is not None else default


def celsius(tenths_kelvin, default=None):
    got = number(tenths_kelvin)
    if got is None:
        return default
    return round(got / 10.0 - _ACPI_OFFSET, 1)


def wmi_chars(value) -> str:
    """WmiMonitorID packs strings as null-terminated char-code arrays."""
    if not isinstance(value, list):
        return text(value)
    return "".join(chr(int(c)) for c in value if isinstance(c, (int, float)) and int(c) > 0).strip()


def mac(value) -> str:
    raw = text(value)
    if not raw:
        return ""
    return ":".join(part.rjust(2, "0") for part in raw.replace("-", ":").replace(".", ":").split(":") if part)


_BIT_PREFIX = {"k": 1e3, "m": 1e6, "g": 1e9, "t": 1e12}


def bit_rate(value, default: float = 0.0) -> float:
    """'10 Gbps' / '1 Gbps' / '100 Mbps' -> bits per second."""
    raw = text(value).lower().replace(",", ".").replace("\u00a0", "").replace(" ", "")
    if "bps" not in raw:
        return default
    head = raw.split("bps")[0]
    got = number(head[:-1]) if head[-1:] in _BIT_PREFIX else number(head)
    if got is None:
        return default
    return got * _BIT_PREFIX[head[-1]] if head[-1:] in _BIT_PREFIX else got


def is_virtual(adapter: dict) -> bool:
    blob = " ".join(
        text(adapter.get(key)) for key in ("InterfaceDescription", "Name", "InterfaceType", "MacAddress")
    ).lower()
    return any(
        token in blob
        for token in (
            "virtual",
            "hyper-v",
            "vmware",
            "vbox",
            "tap-",
            "tunnel",
            "loopback",
            "00-15-5d",
            "00:15:5d",
            "00-50-56",
            "00:50:56",
            "08-00-27",
        )
    )


def datetime_value(value):
    """CIM datetimes arrive as /Date(1755457511000)/, registry ones as MM/DD/YYYY."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).astimezone()
    raw = text(value)
    match = _DATE_RE.match(raw)
    if match:
        return datetime.fromtimestamp(int(match.group(1)) / 1000.0, tz=timezone.utc).astimezone()
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.rstrip("Z").split(".")[0], fmt)
        except ValueError:
            continue
    return None


def seconds_since(value) -> float:
    moment = datetime_value(value)
    if moment is None:
        return 0.0
    delta = datetime.now(moment.tzinfo) - moment
    return max(0.0, delta.total_seconds())


def wlan_interfaces() -> list[dict]:
    """Parse `netsh wlan show interfaces` into dicts keyed by WLAN_ALIASES.

    netsh localizes its labels, so values are matched against FR and EN aliases
    instead of positions. Blocks without enough recognisable labels are discarded.
    """
    raw = text(SNAPSHOT.get("wlanIface"))
    if not raw:
        return []
    lowered = raw.casefold()
    if "refus" in lowered or "denied" in lowered:
        return []
    blocks: list[dict] = []
    current: dict | None = None
    for line in raw.splitlines():
        if not line.strip():
            current = None
            continue
        pair = _PAIR_RE.match(line)
        if not pair:
            continue
        label = " ".join(pair.group(1).casefold().split())
        value = pair.group(2).strip()
        if not value:
            continue
        if current is None:
            current = {}
            blocks.append(current)
        for key, aliases in WLAN_ALIASES.items():
            if label in aliases:
                current.setdefault(key, value)
                break
    return [block for block in blocks if len(block) >= 2]


_PROFILE_AUTH_TOKENS = ("wpa2-psk", "wpa3-sae", "wpa3-psk", "wpa-psk", "wpa2-personal", "wpa-personal", "wep", "open")


def known_profiles() -> int:
    """Count rows of `netsh wlan show profiles`; the auth column is not localized."""
    raw = text(SNAPSHOT.get("wlanProfiles")).casefold()
    if not raw or "refus" in raw or "denied" in raw:
        return 0
    count = 0
    for line in raw.splitlines():
        if not line.startswith("    "):
            continue
        if any(token in line for token in _PROFILE_AUTH_TOKENS):
            count += 1
    return count


def uptime() -> float:
    perf = first("Win32_PerfFormattedData_PerfOS_System")
    value = number(perf.get("SystemUpTime"))
    if value:
        return value
    return seconds_since(first("Win32_OperatingSystem").get("LastBootUpTime"))


def video_output(value) -> str:
    number_value = integer(value, -1)
    return VIDEO_OUTPUT.get(number_value, "")


def pci_address(device_id) -> str:
    raw = text(device_id)
    if not raw.upper().startswith("PCI"):
        return ""
    tail = raw.split("\\")[1] if "\\" in raw else ""
    return f"PCI {tail}" if tail else ""


def last_boot() -> datetime | None:
    return datetime_value(first("Win32_OperatingSystem").get("LastBootUpTime"))


def safe_percent(part, whole) -> float | None:
    part_value, whole_value = number(part), number(whole)
    if part_value is None or not whole_value:
        return None
    return round(part_value * 100.0 / whole_value, 1)
