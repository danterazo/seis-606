"""Runs on a Proxmox node (python3, standard library only) and prints one JSON document about its CPU and GPUs.

The dashboard sends this file over SSH on stdin, so it must not import anything from this project.
"""

import glob
import json
import os
import re
import shlex
import subprocess
from typing import Any, Dict, List, Optional, Tuple

PCI_ROOT = "/sys/bus/pci/devices"
DISPLAY_CLASS_PREFIX = "0x03"
VENDOR_NAMES = {"0x8086": "Intel", "0x10de": "NVIDIA", "0x1002": "AMD"}
BYTES_PER_MIB = 1024 * 1024
PCI_SLOT_LENGTH = len("0000:00:00.0")
INTEL_SAMPLE_MS = "300"
INTEL_WINDOW_SECONDS = "1.0"

NvidiaReading = Tuple[Optional[float], Optional[int], Optional[int]]


def read_text(path: str) -> Optional[str]:
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError:
        return None


def read_int(path: str) -> Optional[int]:
    text = read_text(path)
    return int(text) if text is not None and text.isdigit() else None


def run(command: List[str], *, timeout: float = 4.0) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout


def cpu_model() -> Optional[str]:
    for line in (read_text("/proc/cpuinfo") or "").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def pretty_gpu_name(*, device: str, vendor: str) -> str:
    """Prefer the marketing name in brackets and make sure the vendor is named."""
    match = re.search(r"\[([^\]]+)\]\s*$", device)
    name = match.group(1) if match else device
    if vendor and vendor.lower() not in name.lower():
        name = f"{vendor} {name}"
    return name


def lspci_device_name(*, slot: str) -> Optional[str]:
    for line in run(["lspci", "-mm", "-s", slot]).splitlines():
        fields = shlex.split(line)
        if len(fields) > 3:
            return fields[3]
    return None


def parse_nvidia(*, output: str) -> Dict[str, NvidiaReading]:
    """Map PCI slot -> (utilization percent, memory used bytes, memory total bytes)."""
    readings: Dict[str, NvidiaReading] = {}
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


def parse_intel_busy(*, output: str) -> Optional[float]:
    """intel_gpu_top streams a JSON array that is never closed; use the busiest engine of the last complete sample."""
    start = output.find("[")
    if start == -1:
        return None
    decoder = json.JSONDecoder()
    text = output[start + 1 :]
    samples: List[Dict[str, Any]] = []
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


def display_slots() -> List[str]:
    slots: List[str] = []
    for path in sorted(glob.glob(f"{PCI_ROOT}/*")):
        if (read_text(f"{path}/class") or "").startswith(DISPLAY_CLASS_PREFIX):
            slots.append(os.path.basename(path))
    return slots


def driver_of(*, path: str) -> Optional[str]:
    try:
        return os.path.basename(os.readlink(f"{path}/driver"))
    except OSError:
        return None


def collect_gpus() -> List[Dict[str, Any]]:
    slots = display_slots()
    nvidia = parse_nvidia(output=run(["nvidia-smi", "--query-gpu=pci.bus_id,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"])) if slots else {}
    gpus: List[Dict[str, Any]] = []
    for slot in slots:
        path = f"{PCI_ROOT}/{slot}"
        vendor = VENDOR_NAMES.get(read_text(f"{path}/vendor") or "", "")
        driver = driver_of(path=path)
        device = lspci_device_name(slot=slot) or f"GPU {(read_text(f'{path}/device') or '').removeprefix('0x')}"
        utilization: Optional[float] = None
        used: Optional[int] = None
        total: Optional[int] = None
        if driver == "amdgpu":
            utilization = float(read_int(f"{path}/gpu_busy_percent") or 0) if read_int(f"{path}/gpu_busy_percent") is not None else None
            used, total = read_int(f"{path}/mem_info_vram_used"), read_int(f"{path}/mem_info_vram_total")
        elif driver == "nvidia":
            utilization, used, total = nvidia.get(slot, (None, None, None))
        elif driver in ("i915", "xe"):
            utilization = parse_intel_busy(output=run(["timeout", "-s", "INT", INTEL_WINDOW_SECONDS, "intel_gpu_top", "-J", "-s", INTEL_SAMPLE_MS, "-d", f"pci:slot={slot}"], timeout=6.0))
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


def main() -> None:
    print(json.dumps({"cpu_model": cpu_model(), "gpus": collect_gpus()}))


if __name__ == "__main__":
    main()
