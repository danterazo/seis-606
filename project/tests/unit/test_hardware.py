import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from homelab_dashboard.models import (
    ClusterSnapshot,
    Gpu,
    GpuState,
    Hardware,
    HardwareSource,
    Node,
    NodeState,
    Resources,
)
from homelab_dashboard.node_profiles import expected_hardware_for
from homelab_dashboard.sources import remote_probe
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.hardware_parser import parse_hardware, tidy_cpu_model
from homelab_dashboard.sources.hardware_source import HardwareEnrichedSource
from homelab_dashboard.sources.hardware_ssh import PROBE_SCRIPT, SshHardwareProbe
from homelab_dashboard.sources.proxmox_ssh import CommandRunner

START: datetime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)


def make_node(*, name: str, state: NodeState = NodeState.ONLINE, address: str | None = "10.0.0.5") -> Node:
    return Node(name=name, state=state, address=address, resources=Resources(), guests=())


class FakeCluster:
    def __init__(self, *, nodes: tuple[Node, ...]) -> None:
        self.nodes: tuple[Node, ...] = nodes
        self.fresh_calls: int = 0

    def _snapshot(self) -> ClusterSnapshot:
        return ClusterSnapshot(source="fake", fetched_at=START, nodes=self.nodes)

    def fetch(self) -> ClusterSnapshot:
        return self._snapshot()

    def fetch_fresh(self) -> ClusterSnapshot:
        self.fresh_calls += 1
        return self._snapshot()


class FakeProbe:
    def __init__(self, *, results: dict[str, Hardware | None]) -> None:
        self.results: dict[str, Hardware | None] = results
        self.calls: list[str] = []

    def probe(self, *, node_name: str, address: str) -> Hardware:
        self.calls.append(node_name)
        result: Hardware | None = self.results.get(node_name)
        if result is None:
            raise StatusSourceError("probe failed")
        return result


class Ticker:
    def __init__(self) -> None:
        self.value: float = 0.0

    def __call__(self) -> float:
        return self.value


LIVE: Hardware = Hardware(cpu_model="Intel N150", cpu_cores=6, cpu_threads=12, source=HardwareSource.LIVE)


def test_tidy_cpu_model_strips_marketing_noise() -> None:
    assert tidy_cpu_model(model="Intel(R) Xeon(R) CPU E5-1650 v4 @ 3.60GHz") == "Intel Xeon E5-1650 v4"
    assert tidy_cpu_model(model="Intel(R) N150") == "Intel N150"
    assert tidy_cpu_model(model="AMD Ryzen Threadripper PRO 3945WX 12-Cores") == "AMD Ryzen Threadripper PRO 3945WX"


def test_parse_hardware_distinguishes_active_passthrough_and_driverless_gpus() -> None:
    hardware: Hardware = parse_hardware(
        document={
            "cpu_model": "Intel(R) N150",
            "gpus": [
                {"name": "AMD Radeon PRO V620", "driver": "amdgpu", "utilization_percent": 12.5, "memory_used_bytes": 100, "memory_total_bytes": 400},
                {"name": "NVIDIA GeForce RTX 5060 Ti", "driver": "vfio-pci", "utilization_percent": 99, "memory_total_bytes": 1},
                {"name": "Mystery", "driver": None},
                {"driver": "amdgpu"},
                "junk",
            ],
        }
    )
    assert hardware.source is HardwareSource.LIVE
    assert hardware.cpu_model == "Intel N150"
    assert (hardware.cpu_cores, hardware.cpu_threads) == (None, None)
    active, passthrough, driverless = hardware.gpus
    assert (active.state, active.utilization_percent, active.memory_used_bytes, active.memory_total_bytes) == (GpuState.ACTIVE, 12.5, 100, 400)
    assert passthrough == Gpu(name="NVIDIA GeForce RTX 5060 Ti", state=GpuState.PASSTHROUGH)
    assert driverless.state is GpuState.NO_DRIVER


def test_parse_hardware_keeps_unknown_readings_as_none() -> None:
    hardware: Hardware = parse_hardware(document={"gpus": [{"name": "Intel Graphics", "driver": "i915"}]})
    assert hardware.cpu_model is None
    assert hardware.gpus[0].utilization_percent is None


def test_parse_hardware_reads_cpu_topology() -> None:
    hardware: Hardware = parse_hardware(document={"cpu_cores": 12, "cpu_threads": 24})

    assert (hardware.cpu_cores, hardware.cpu_threads) == (12, 24)


def test_parse_hardware_rejects_non_objects() -> None:
    with pytest.raises(StatusSourceError):
        parse_hardware(document=["nope"])


def test_probe_parses_nvidia_csv_by_pci_slot() -> None:
    readings = remote_probe.parse_nvidia(output="00000000:01:00.0, 37, 2048, 16311\n")
    assert readings == {"0000:01:00.0": (37.0, 2048 * 1024 * 1024, 16311 * 1024 * 1024)}


def test_probe_reads_busiest_engine_of_last_complete_sample_from_unclosed_stream() -> None:
    stream: str = (
        '[\n{"engines": {"Render/3D": {"busy": 1.0}}},\n'
        '{"engines": {"Render/3D": {"busy": 40.5}, "Video": {"busy": 12.0}}},\n'
        '{"engines": {"Render/3'
    )
    assert remote_probe.parse_intel_busy(output=stream) == 40.5
    assert remote_probe.parse_intel_busy(output="no json") is None


def test_probe_counts_physical_cores_and_logical_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    cpuinfo: str = "\n\n".join(
        f"processor : {thread}\nphysical id : 0\ncore id : {thread // 2}"
        for thread in range(4)
    )
    monkeypatch.setattr(remote_probe, "read_text", lambda *, path: cpuinfo if path == "/proc/cpuinfo" else None)

    assert remote_probe.cpu_topology() == (2, 4)


def test_probe_names_gpus_with_vendor_and_marketing_name() -> None:
    assert remote_probe.pretty_gpu_name(device="Navi 21 GL-XL [Radeon PRO V620]", vendor="AMD") == "AMD Radeon PRO V620"
    assert remote_probe.pretty_gpu_name(device="Alder Lake-N [Intel Graphics]", vendor="Intel") == "Intel Graphics (Alder Lake-N)"


def test_expected_hardware_matches_the_configured_machines() -> None:
    kveikur: Hardware = expected_hardware_for(node_name="kveikur")
    assert kveikur.source is HardwareSource.EXPECTED
    assert kveikur.cpu_model == "AMD Ryzen Threadripper PRO 3945WX"
    assert kveikur.gpus == ()
    assert expected_hardware_for(node_name="Kex").cpu_model == "Intel Xeon E5-1650 v4"
    assert expected_hardware_for(node_name="Kex").gpus == ()
    assert expected_hardware_for(node_name="stranger") == Hardware()


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("\tError Correction Type: Multi-bit ECC", True),
        ("\tError Correction Type: Single-bit ECC", True),
        ("\tError Correction Type: None", False),
        ("\tError Correction Type: Unknown", None),
        ("\tError Correction Type: Parity", None),
        ("", None),
        ("Error Correction Type: None\nError Correction Type: Unknown", None),
        ("Error Correction Type: None\nError Correction Type: Multi-bit ECC", True),
    ],
)
def test_probe_reports_firmware_ecc_without_guessing(
    monkeypatch: pytest.MonkeyPatch, output: str, expected: bool | None
) -> None:
    def fake_run(*, command: list[str], timeout: float = 4.0) -> str:
        assert command == ["dmidecode", "--type", "16"]
        return output

    monkeypatch.setattr(remote_probe, "run", fake_run)
    assert remote_probe.ecc_supported() is expected


@pytest.mark.parametrize("value", [True, False, None, "yes", 1])
def test_parser_accepts_only_boolean_ecc_readings(value: object) -> None:
    hardware: Hardware = parse_hardware(document={"ecc_supported": value})
    assert hardware.ecc_supported is (value if isinstance(value, bool) else None)


def test_probe_does_not_collect_gpus(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(remote_probe, "cpu_model", lambda: "Intel N150")
    monkeypatch.setattr(remote_probe, "cpu_topology", lambda: (4, 8))
    monkeypatch.setattr(remote_probe, "ecc_supported", lambda: None)
    monkeypatch.setattr(remote_probe, "zfs_arc_stat", lambda *, name: 1024 if name == "size" else 2048)

    def forbidden_collection() -> None:
        pytest.fail("GPU collection is deferred")

    monkeypatch.setattr(remote_probe, "collect_gpus", forbidden_collection)
    remote_probe.main()
    assert json.loads(capsys.readouterr().out) == {"cpu_model": "Intel N150", "cpu_cores": 4, "cpu_threads": 8, "ecc_supported": None, "zfs_arc_bytes": 1024, "zfs_arc_max_bytes": 2048, "gpus": []}


def test_only_online_nodes_are_probed_and_others_use_expected_hardware() -> None:
    probe: FakeProbe = FakeProbe(results={"cerulean": LIVE})
    source: HardwareEnrichedSource = HardwareEnrichedSource(
        cluster=FakeCluster(nodes=(make_node(name="cerulean"), make_node(name="kex", state=NodeState.OFFLINE, address=None))),
        probe=probe,
        expected_hardware=expected_hardware_for,
        ttl_seconds=3,
    )
    cerulean, kex = source.fetch().nodes
    assert probe.calls == ["cerulean"]
    assert cerulean.hardware == LIVE
    assert kex.hardware.source is HardwareSource.EXPECTED


def test_failed_probe_falls_back_without_failing_the_snapshot() -> None:
    source: HardwareEnrichedSource = HardwareEnrichedSource(
        cluster=FakeCluster(nodes=(make_node(name="kveikur"),)),
        probe=FakeProbe(results={}),
        expected_hardware=expected_hardware_for,
        ttl_seconds=3,
    )
    assert source.fetch().nodes[0].hardware.source is HardwareSource.EXPECTED


def test_probe_results_are_cached_until_the_ttl_or_a_forced_refresh() -> None:
    ticker: Ticker = Ticker()
    probe: FakeProbe = FakeProbe(results={"cerulean": LIVE})
    source: HardwareEnrichedSource = HardwareEnrichedSource(
        cluster=FakeCluster(nodes=(make_node(name="cerulean"),)),
        probe=probe,
        expected_hardware=expected_hardware_for,
        ttl_seconds=3,
        clock=ticker,
    )
    assert source.fetch().nodes[0].hardware == LIVE
    ticker.value = 2.9
    assert source.fetch().nodes[0].hardware.cpu_cores == 6
    assert probe.calls == ["cerulean"]
    ticker.value = 3.0
    source.fetch()
    assert probe.calls == ["cerulean", "cerulean"]
    source.fetch_fresh()
    assert len(probe.calls) == 3


def test_snapshot_time_advances_with_each_probe_so_the_browser_redraws() -> None:
    later: datetime = datetime(2025, 1, 1, 12, 0, 5, tzinfo=UTC)
    source: HardwareEnrichedSource = HardwareEnrichedSource(
        cluster=FakeCluster(nodes=(make_node(name="cerulean"),)),
        probe=FakeProbe(results={"cerulean": LIVE}),
        expected_hardware=expected_hardware_for,
        ttl_seconds=3,
        now=lambda: later,
    )
    assert source.fetch().fetched_at == later


def make_runner(*, stdout: str = "", stderr: str = "", returncode: int = 0, calls: list[tuple[Sequence[str], str | None]]) -> CommandRunner:
    def runner(command: Sequence[str], *, timeout: float, stdin: str | None = None) -> "subprocess.CompletedProcess[str]":
        calls.append((command, stdin))
        return subprocess.CompletedProcess(args=list(command), returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


def test_ssh_probe_sends_the_script_on_stdin_with_strict_host_keys() -> None:
    calls: list[tuple[Sequence[str], str | None]] = []
    probe: SshHardwareProbe = SshHardwareProbe(runner=make_runner(stdout=json.dumps({"cpu_model": "Intel(R) N150", "gpus": []}), calls=calls))
    hardware: Hardware = probe.probe(node_name="cerulean", address="192.168.20.43")
    command, stdin = calls[0]
    assert hardware.cpu_model == "Intel N150"
    assert "-oStrictHostKeyChecking=yes" in command
    assert command[-2:] == ("root@192.168.20.43", "python3 -")
    assert stdin == PROBE_SCRIPT


def test_ssh_probe_reports_failures_and_malformed_output() -> None:
    with pytest.raises(StatusSourceError, match="refused"):
        SshHardwareProbe(runner=make_runner(stderr="Permission denied (publickey)", returncode=255, calls=[])).probe(node_name="x", address="10.0.0.1")
    with pytest.raises(StatusSourceError, match="malformed"):
        SshHardwareProbe(runner=make_runner(stdout="not json", calls=[])).probe(node_name="x", address="10.0.0.1")
