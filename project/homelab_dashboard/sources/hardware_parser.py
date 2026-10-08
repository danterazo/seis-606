import re
from collections.abc import Mapping
from typing import Final, List, Optional, Tuple

from homelab_dashboard.models import Gpu, GpuState, Hardware, HardwareSource
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.json_values import as_integer, as_number, as_text

JsonObject = Mapping[str, object]

PASSTHROUGH_DRIVER: Final[str] = "vfio-pci"
# Drivers whose utilization the probe knows how to read.
MONITORED_DRIVERS: Final[Tuple[str, ...]] = ("amdgpu", "nvidia", "i915", "xe")

# Marketing noise that adds length but no information to a CPU name.
_CPU_NOISE: Final[Tuple[str, ...]] = (r"\(R\)", r"\(TM\)", r"@\s*[\d.]+\s*[GM]Hz")
_CPU_FILLER: Final[Tuple[str, ...]] = (r"\bCPU\b", r"\bProcessor\b", r"\b\d+-Cores?\b")


def tidy_cpu_model(*, model: str) -> str:
    """`Intel(R) Xeon(R) CPU E5-1650 v4 @ 3.60GHz` -> `Intel Xeon E5-1650 v4`."""
    tidied: str = model
    for pattern in _CPU_NOISE:
        tidied = re.sub(pattern, "", tidied)
    for pattern in _CPU_FILLER:
        tidied = re.sub(pattern, " ", tidied)
    return re.sub(r"\s+", " ", tidied).strip()


def _gpu_state(*, driver: Optional[str]) -> GpuState:
    if driver == PASSTHROUGH_DRIVER:
        return GpuState.PASSTHROUGH
    if driver in MONITORED_DRIVERS:
        return GpuState.ACTIVE
    return GpuState.NO_DRIVER


def _parse_gpu(*, row: object) -> Optional[Gpu]:
    if not isinstance(row, Mapping):
        return None
    name: Optional[str] = as_text(value=row.get("name"))
    if name is None:
        return None
    state: GpuState = _gpu_state(driver=as_text(value=row.get("driver")))
    # A passed-through or driverless card has no readings the host can trust.
    if state is not GpuState.ACTIVE:
        return Gpu(name=name, state=state)
    return Gpu(
        name=name,
        state=state,
        utilization_percent=as_number(value=row.get("utilization_percent")),
        memory_used_bytes=as_integer(value=row.get("memory_used_bytes")),
        memory_total_bytes=as_integer(value=row.get("memory_total_bytes")),
    )


def parse_hardware(*, document: object) -> Hardware:
    if not isinstance(document, Mapping):
        raise StatusSourceError("The hardware probe returned an unexpected response.")
    model: Optional[str] = as_text(value=document.get("cpu_model"))
    ecc: object = document.get("ecc_supported")
    rows: object = document.get("gpus")
    gpus: List[Gpu] = []
    for row in rows if isinstance(rows, list) else []:
        parsed: Optional[Gpu] = _parse_gpu(row=row)
        if parsed is not None:
            gpus.append(parsed)
    return Hardware(
        cpu_model=None if model is None else tidy_cpu_model(model=model),
        cpu_cores=as_integer(value=document.get("cpu_cores")),
        cpu_threads=as_integer(value=document.get("cpu_threads")),
        gpus=tuple(gpus),
        source=HardwareSource.LIVE,
        ecc_supported=ecc if isinstance(ecc, bool) else None,
        zfs_arc_bytes=as_integer(value=document.get("zfs_arc_bytes")),
        zfs_arc_max_bytes=as_integer(value=document.get("zfs_arc_max_bytes")),
    )

