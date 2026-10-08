"""Runs on a Proxmox node (python3, standard library only) and prints CPU and firmware ECC information.

The dashboard sends this file over SSH on stdin, so it must not import anything from this project.
"""

import glob
import json
import os
import re
import shlex
import subprocess
from typing import Any

PCI_ROOT = "/sys/bus/pci/devices"
DISPLAY_CLASS_PREFIX = "0x03"
VENDOR_NAMES = {"0x8086": "Intel", "0x10de": "NVIDIA", "0x1002": "AMD"}
BYTES_PER_MIB = 1024 * 1024
PCI_SLOT_LENGTH = len("0000:00:00.0")
INTEL_SAMPLE_MS = "300"
INTEL_WINDOW_SECONDS = "1.0"

NvidiaReading = tuple[float | None, int | None, int | None]


def read_text(*, path: str) -> str | None:
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return None


def read_int(*, path: str) -> int | None:
    text = read_text(path=path)
    return int(text) if text is not None and text.isdigit() else None


def run(*, command: list[str], timeout: float = 4.0) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as error:
        # intel_gpu_top is stopped with SIGINT by `timeout`; keep whatever it printed.
        partial = error.stdout
        return partial.decode() if isinstance(partial, bytes) else (partial or "")
    except OSError:
        return ""
    return completed.stdout


def cpu_model() -> str | None:
    for line in (read_text(path="/proc/cpuinfo") or "").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def cpu_topology() -> tuple[int | None, int | None]:
    records: list[dict[str, str]] = []
    for line in (read_text(path="/proc/cpuinfo") or "").splitlines():
        if not line.strip():
            if records and records[-1]:
                records.append({})
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if not records:
            records.append({})
        records[-1][key.strip()] = value.strip()

    records = [record for record in records if record]
    threads: int | None = sum("processor" in record for record in records) or None
    core_pairs = {
        (record.get("physical id", "0"), record["core id"])
        for record in records
        if "core id" in record
    }
    if core_pairs:
        cores: int | None = len(core_pairs)
    else:
        core_counts = {int(record["cpu cores"]) for record in records if record.get("cpu cores", "").isdigit()}
        sockets = {record.get("physical id", "0") for record in records}
        cores = next(iter(core_counts)) * len(sockets) if core_counts and sockets else None
    return cores, threads


def pretty_gpu_name(*, device: str, vendor: str) -> str:
    """Prefer the marketing name in brackets and make sure the vendor is named."""
    match = re.search(r"^(.*?)\s*\[([^\]]+)\]\s*$", device)
    if match is None:
        return device if not vendor or vendor.lower() in device.lower() else f"{vendor} {device}"
    chip, marketing = match.group(1), match.group(2)
    if vendor and vendor.lower() in marketing.lower():
        return f"{marketing} ({chip})" if chip else marketing
    return f"{vendor} {marketing}" if vendor else marketing


def lspci_device_name(*, slot: str) -> str | None:
    for line in run(command=["lspci", "-mm", "-s", slot]).splitlines():
        fields = shlex.split(line)
        if len(fields) > 3:
            return fields[3]
    return None


def parse_nvidia(*, output: str) -> dict[str, NvidiaReading]:
    """Map PCI slot -> (utilization percent, memory used bytes, memory total bytes)."""
    readings: dict[str, NvidiaReading] = {}
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        bus_id, utilization, used, total = parts
        readings[bus_id.lower()[-PCI_SLOT_LENGTH:]] = (
            float(utilization) if utilization.replace(".", "", 1).isdigit() else None,
            int(used) * BYTES_PER_MIB if used.isdigit() else None,
            int(total) * BYTES_PER_MIB if total.isdigit() else None,
        )
    return readings


def parse_intel_busy(*, output: str) -> float | None:
    """intel_gpu_top streams a JSON array that is never closed; use the busiest engine of the last complete sample."""
    start = output.find("[")
    if start == -1:
        return None
    decoder = json.JSONDecoder()
    text = output[start + 1 :]
    samples: list[dict[str, Any]] = []
    index = 0
    while True:
        while index < len(text) and text[index] in " \r\n\t,":
            index += 1
        if index >= len(text):
            break
        try:
            sample, index = decoder.raw_decode(text, index)
        except ValueError:
            break
        samples.append(sample)
    if not samples:
        return None
    engines = samples[-1].get("engines", {})
    busy = [engine["busy"] for engine in engines.values() if isinstance(engine.get("busy"), (int, float))]
    return float(max(busy)) if busy else None


def display_slots() -> list[str]:
    return [
        os.path.basename(path)
        for path in sorted(glob.glob(f"{PCI_ROOT}/*"))
        if (read_text(path=f"{path}/class") or "").startswith(DISPLAY_CLASS_PREFIX)
    ]


def driver_of(*, path: str) -> str | None:
    try:
        return os.path.basename(os.readlink(f"{path}/driver"))
    except OSError:
        return None


def collect_gpus() -> list[dict[str, Any]]:
    slots = display_slots()
    nvidia: dict[str, NvidiaReading] = {}
    if slots:
        query = ["nvidia-smi", "--query-gpu=pci.bus_id,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]
        nvidia = parse_nvidia(output=run(command=query))
    gpus: list[dict[str, Any]] = []
    for slot in slots:
        path = f"{PCI_ROOT}/{slot}"
        vendor = VENDOR_NAMES.get(read_text(path=f"{path}/vendor") or "", "")
        driver = driver_of(path=path)
        device = lspci_device_name(slot=slot) or f"GPU {(read_text(path=f'{path}/device') or '').removeprefix('0x')}"
        utilization: float | None = None
        used: int | None = None
        total: int | None = None
        if driver == "amdgpu":
            busy = read_int(path=f"{path}/gpu_busy_percent")
            utilization = None if busy is None else float(busy)
            used, total = read_int(path=f"{path}/mem_info_vram_used"), read_int(path=f"{path}/mem_info_vram_total")
        elif driver == "nvidia":
            utilization, used, total = nvidia.get(slot, (None, None, None))
        elif driver in ("i915", "xe"):
            command = ["timeout", "-s", "INT", INTEL_WINDOW_SECONDS, "intel_gpu_top", "-J", "-s", INTEL_SAMPLE_MS, "-d", f"pci:slot={slot}"]
            utilization = parse_intel_busy(output=run(command=command, timeout=6.0))
        gpus.append(
            {
                "name": pretty_gpu_name(device=device, vendor=vendor),
                "vendor": vendor,
                "driver": driver,
                "utilization_percent": utilization,
                "memory_used_bytes": used,
                "memory_total_bytes": total,
            }
        )
    return gpus


def ecc_supported() -> bool | None:
    output: str = run(command=["dmidecode", "--type", "16"])
    corrections: list[str] = [
        line.split(":", 1)[1].strip().casefold()
        for line in output.splitlines()
        if line.strip().startswith("Error Correction Type:")
    ]
    if not corrections:
        return None
    if any(value in ("single-bit ecc", "multi-bit ecc") for value in corrections):
        return True
    return False if all(value == "none" for value in corrections) else None


def zfs_arc_stat(*, name: str) -> int | None:
    for line in (read_text(path="/proc/spl/kstat/zfs/arcstats") or "").splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0] == name and fields[2].isdigit():
            return int(fields[2])
    return None


def main() -> None:
    cores, threads = cpu_topology()
    arc = {"zfs_arc_bytes": zfs_arc_stat(name="size"), "zfs_arc_max_bytes": zfs_arc_stat(name="c_max")}
    print(json.dumps({"cpu_model": cpu_model(), "cpu_cores": cores, "cpu_threads": threads, "ecc_supported": ecc_supported(), **arc, "gpus": []}))


if __name__ == "__main__":
    main()
