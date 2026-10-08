import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from homelab_dashboard.node_profiles import DISPLAY_NAMES
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.openwrt_ssh import (
    REMOTE_COMMAND,
    OpenWrtLeaseSource,
    build_device_payloads,
    parse_ipv6_records,
    parse_leases,
)
from homelab_dashboard.sources.proxmox_ssh import SshTarget

NOW: datetime = datetime(2026, 10, 7, tzinfo=UTC)
LEASES: str = "2000000000 AA:BB:CC:DD:EE:FF 192.168.10.23 ringom4-wifi *\n0 11:22:33:44:55:66 192.168.10.24 * *\n"


def test_dnsmasq_leases_preserve_identity_and_use_shared_names() -> None:
    named, unnamed = parse_leases(text=LEASES)
    assert named.mac == "aa:bb:cc:dd:ee:ff"
    assert named.to_payload()["mac"] == "AA:BB:CC:DD:EE:FF"
    assert named.hostname == "ringom4-wifi"
    assert named.to_payload()["display_name"] == DISPLAY_NAMES["ringom4-wifi"]
    assert named.expires_at == datetime.fromtimestamp(2000000000, UTC)
    assert unnamed.expires_at is None
    assert unnamed.hostname is None
    assert unnamed.to_payload()["display_name"] == "192.168.10.24"
    assert parse_leases(text="\n") == ()


@pytest.mark.parametrize(
    "text",
    [
        "bad row",
        "x aa:bb:cc:dd:ee:ff 192.168.10.2 suika *",
        "0 bad 192.168.10.2 suika *",
        "0 aa:bb:cc:dd:ee:ff bad suika *",
        "-1 aa:bb:cc:dd:ee:ff 192.168.10.2 suika *",
    ],
)
def test_malformed_leases_are_not_presented_as_empty_inventory(text: str) -> None:
    with pytest.raises(StatusSourceError):
        parse_leases(text=text)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[Sequence[str]] = []
        self.returncode: int = 0
        self.stdout: str = LEASES
        self.stderr: str = ""

    def __call__(self, command: Sequence[str], *, timeout: float, stdin: str | None = None) -> "subprocess.CompletedProcess[str]":
        assert timeout == 8.0
        self.calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def test_router_source_caches_failures_and_retains_last_good_data() -> None:
    runner = FakeRunner()
    ticks: list[float] = [0.0]
    source = OpenWrtLeaseSource(target=SshTarget(host="192.168.10.1"), runner=runner, now=lambda: NOW, clock=lambda: ticks[0])
    first = source.fetch()
    assert len(first["leases"]) == 2
    assert first["stale"] is False
    assert first["router"] == "192.168.10.1"
    assert first["source"] == "OpenWRT"
    assert "ipv6_error" not in first
    source.fetch()
    assert len(runner.calls) == 1
    command = runner.calls[0]
    assert "-oStrictHostKeyChecking=yes" in command
    assert "-oBatchMode=yes" in command
    assert command[-2:] == ("root@192.168.10.1", REMOTE_COMMAND)
    ticks[0] = 60.0
    runner.returncode = 255
    runner.stderr = "Host key verification failed."
    failed = source.fetch()
    assert failed["stale"] is True
    assert "host key" in failed["error"]
    assert failed["leases"] == first["leases"]
    assert failed["fetched_at"] == first["fetched_at"]
    source.fetch()
    assert len(runner.calls) == 2
    runner.returncode = 0
    assert source.fetch(force=True)["stale"] is False
    assert len(runner.calls) == 3


def test_first_failure_has_no_fake_leases_or_success_timestamp() -> None:
    runner = FakeRunner()
    runner.returncode = 255
    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner)
    payload = source.fetch()
    assert payload["leases"] == []
    assert payload["fetched_at"] is None
    assert payload["error"] is not None


def test_expired_leases_are_filtered_even_when_the_cache_is_fresh() -> None:
    runner = FakeRunner()
    runner.stdout = "100 aa:bb:cc:dd:ee:ff 192.168.10.2 suika *"
    seconds: list[int] = [99]
    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner, now=lambda: datetime.fromtimestamp(seconds[0], UTC))
    assert len(source.fetch()["leases"]) == 1
    seconds[0] = 100
    assert source.fetch()["leases"] == []
    assert len(runner.calls) == 1


def test_leases_are_grouped_lan_first_and_sorted_by_numeric_ip() -> None:
    runner = FakeRunner()
    addresses: list[str] = ["172.16.10.170", "192.168.20.30", "192.168.10.10", "172.16.0.2", "192.168.10.2"]
    runner.stdout = "\n".join(f"0 aa:bb:cc:dd:ee:ff {address} device *" for address in addresses)
    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner)
    leases = source.fetch()["leases"]
    assert [lease["address"] for lease in leases] == ["192.168.10.2", "192.168.10.10", "192.168.20.30", "172.16.0.2", "172.16.10.170"]
    assert [lease["network_group"] for lease in leases] == ["lan", "lan", "lan", "guest_iot", "guest_iot"]


@pytest.mark.parametrize("address", ["192.168.0.1", "192.168.255.254", "172.16.0.1", "10.0.0.1", "192.169.0.1"])
def test_network_groups_include_all_non_lan_devices_in_the_second_panel(address: str) -> None:
    lease = parse_leases(text=f"0 aa:bb:cc:dd:ee:ff {address} device *")[0]
    assert lease.to_payload()["network_group"] == ("lan" if address.startswith("192.168.") else "guest_iot")


def test_named_devices_precede_ip_only_devices_in_both_panels() -> None:
    runner = FakeRunner()
    runner.stdout = """0 aa:bb:cc:dd:ee:01 172.16.0.2 * *
0 aa:bb:cc:dd:ee:02 172.16.0.3 172.16.0.3 *
0 aa:bb:cc:dd:ee:03 172.16.10.170 creality-k1c-wifi *
0 aa:bb:cc:dd:ee:04 172.16.0.238 ecoflow *
0 aa:bb:cc:dd:ee:05 192.168.10.10 lan-node *
0 aa:bb:cc:dd:ee:06 192.168.10.2 * *
0 aa:bb:cc:dd:ee:07 172.16.0.112 KP125M *
0 aa:bb:cc:dd:ee:08 192.168.10.3 192.168.10.3 *"""
    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner)
    addresses = [lease["address"] for lease in source.fetch()["leases"]]
    assert addresses == [
        "192.168.10.10",
        "192.168.10.2",
        "192.168.10.3",
        "172.16.0.112",
        "172.16.0.238",
        "172.16.10.170",
        "172.16.0.2",
        "172.16.0.3",
    ]


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired(cmd="ssh", timeout=8)])
def test_transport_errors_stay_local_to_the_devices_payload(error: Exception) -> None:
    def runner(command: Sequence[str], *, timeout: float, stdin: str | None = None) -> "subprocess.CompletedProcess[str]":
        raise error

    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner)
    assert source.fetch()["stale"] is True


def test_ipv6_neighbors_and_ethernet_duids_match_ipv4_by_mac_not_hostname() -> None:
    document = {
        "device": {
            "br-lan": {
                "leases": [
                    {
                        "duid": "000100012d24bd02aabbccddeeff",
                        "hostname": "different-name",
                        "ipv6-addr": [
                            {"address": "fdda:beef:1::30", "valid-lifetime": 60},
                            {"address": "fdda:beef:1::31", "valid-lifetime": 0},
                        ],
                    },
                ]
            }
        }
    }
    neighbors = [{"dst": "fe80::1234", "dev": "br-lan", "lladdr": "aa:bb:cc:dd:ee:ff", "state": ["STALE"]}]
    records = parse_ipv6_records(leases=document, neighbors=neighbors, now=NOW)
    devices = build_device_payloads(leases=parse_leases(text=LEASES), ipv6=records, now=NOW)
    named = next(device for device in devices if device["address"] == "192.168.10.23")
    assert named["ipv6_addresses"] == ["fdda:beef:1::30", "fe80::1234"]
    assert named["hostname"] == "ringom4-wifi"
    assert len(devices) == 2


def test_enterprise_duid_does_not_get_guessed_as_a_mac_and_remains_ipv6_only() -> None:
    document = {
        "device": {
            "br-lan": {
                "leases": [
                    {
                        "duid": "00020000ab115ef9d56e9c45ec09",
                        "hostname": "ringom4-wifi",
                        "ipv6-addr": [
                            {"address": "fdda:beef:1::18b", "valid-lifetime": 60},
                        ],
                    },
                ]
            }
        }
    }
    records = parse_ipv6_records(leases=document, neighbors=[], now=NOW)
    devices = build_device_payloads(leases=parse_leases(text=LEASES), ipv6=records, now=NOW)
    unmatched = next(device for device in devices if device["address"] is None)
    assert unmatched["mac"] is None
    assert unmatched["network_group"] == "lan"
    assert unmatched["ipv6_addresses"] == ["fdda:beef:1::18b"]
    assert len(devices) == 3


def test_exact_neighbor_address_links_an_enterprise_duid_and_deduplicates_addresses() -> None:
    document = {
        "device": {
            "br-lan": {
                "leases": [
                    {
                        "duid": "00020000ab115ef9d56e9c45ec09",
                        "hostname": "test",
                        "ipv6-addr": [
                            {"address": "fdda:beef:1::30", "valid-lifetime": 60},
                        ],
                    },
                ]
            }
        }
    }
    neighbors = [{"dst": "fdda:beef:1::30", "dev": "br-lan", "lladdr": "aa:bb:cc:dd:ee:ff", "state": ["REACHABLE"]}]
    devices = build_device_payloads(leases=parse_leases(text=LEASES), ipv6=parse_ipv6_records(leases=document, neighbors=neighbors, now=NOW), now=NOW)
    assert len(devices) == 2
    assert devices[0]["ipv6_addresses"] == ["fdda:beef:1::30"]


def test_ipv6_records_expire_and_failed_or_wan_neighbors_are_not_inventory() -> None:
    document = {
        "device": {
            "br-iot": {
                "leases": [
                    {
                        "duid": "00030001aabbccddeeff",
                        "hostname": "test",
                        "ipv6-addr": [
                            {"address": "fdda:beef:2::1", "valid-lifetime": 1},
                            {"address": "invalid", "valid-lifetime": 60},
                        ],
                    },
                ]
            }
        }
    }
    neighbors = [
        {"dst": "fe80::1", "dev": "eth1", "lladdr": "aa:bb:cc:dd:ee:ff", "state": ["STALE"]},
        {"dst": "fe80::2", "dev": "br-iot", "lladdr": "aa:bb:cc:dd:ee:ff", "state": ["FAILED"]},
    ]
    records = parse_ipv6_records(leases=document, neighbors=neighbors, now=NOW)
    assert len(records) == 1
    assert records[0].mac == "aa:bb:cc:dd:ee:ff"
    devices = build_device_payloads(leases=(), ipv6=records, now=NOW)
    assert devices[0]["network_group"] == "guest_iot"
    assert build_device_payloads(leases=(), ipv6=records, now=datetime.fromtimestamp(NOW.timestamp() + 1, UTC)) == []


def test_malformed_ipv6_documents_are_reported() -> None:
    with pytest.raises(StatusSourceError, match="IPv6 discovery"):
        parse_ipv6_records(leases={}, neighbors=[], now=NOW)


def test_active_source_returns_only_ipv4_and_never_queries_ipv6() -> None:
    runner = FakeRunner()
    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner, now=lambda: NOW)
    payload = source.fetch()
    assert payload["error"] is None
    assert len(payload["leases"]) == 2
    assert all(lease["address"] is not None and "ipv6_addresses" not in lease for lease in payload["leases"])
    assert runner.calls[0][-1] == "cat /tmp/dhcp.leases"


def test_multiple_ipv6_leases_for_the_same_duid_share_one_card() -> None:
    document = {
        "device": {
            "br-lan": {
                "leases": [
                    {"duid": "00020000ab115ef9d56e9c45ec09", "hostname": "test", "ipv6-addr": [{"address": address, "valid-lifetime": 60}]}
                    for address in ("fdda:beef:1::1", "fdda:beef:1::2")
                ]
            }
        }
    }
    records = parse_ipv6_records(leases=document, neighbors=[], now=NOW)
    devices = build_device_payloads(leases=(), ipv6=records, now=NOW)
    assert len(devices) == 1
    assert devices[0]["ipv6_addresses"] == ["fdda:beef:1::1", "fdda:beef:1::2"]
