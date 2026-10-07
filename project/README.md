# Homelab Dashboard

A read-only status page for a Proxmox VE cluster, styled after Frutiger Aero / Y2K desktops.
Resource readings come from Proxmox; display profiles, pinned addresses, fallback CPU
models, and memory inventory are configured separately and are not live discoveries.

## Run

```bash
python3 project/app.py
```

Open the printed URL (default `http://127.0.0.1:8765`). The server needs only the Python
standard library and an OpenSSH client.

| Variable                | Default              | Purpose                                    |
| :---------------------- | :------------------- | :----------------------------------------- |
| `HOMELAB_PVE_SSH_HOST`  | `192.168.20.43`      | Host, IP, or SSH alias of any cluster node |
| `HOMELAB_PVE_SSH_USER`  | `root`               | Account used for every connection          |
| `HOMELAB_SSH_TIMEOUT`   | `15`                 | Seconds to wait for Proxmox                |
| `HOMELAB_CACHE_SECONDS` | `10`                 | Minimum seconds between Proxmox queries (one costs ~2 CPU-seconds on a node); the page itself polls every second |
| `HOMELAB_HARDWARE_CACHE_SECONDS` | `3` | Minimum seconds between CPU/firmware ECC probes of each online node (a tiny read-only Python script sent over the same SSH connection settings; nothing is installed or written on the node) |
| `HOMELAB_ROUTER_SSH_HOST` | `192.168.10.1` | OpenWRT router for DHCPv4 leases |
| `HOMELAB_ROUTER_SSH_USER` | `root` | Router SSH account (key authentication only) |
| `HOMELAB_ROUTER_CACHE_SECONDS` | `60` | Router lease cache TTL, including failures; independent of PVE |
| `HOMELAB_HOST` / `PORT` | `127.0.0.1` / `8765` | Where the dashboard listens                |

### First Connection

Trust Cerulean's host key once, after confirming the fingerprints match:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub        # on Cerulean's console
ssh-keyscan -t ed25519 192.168.20.43 | ssh-keygen -lf -  # on this machine
ssh-keyscan -H -t ed25519 192.168.20.43 >> ~/.ssh/known_hosts
```

Connections use `root` by default. To use another account, set `HOMELAB_PVE_SSH_USER`;
a non-root account needs the `PVEAuditor` role to read cluster resources.

### Device Names and Leases

Edit `DISPLAY_NAMES` in `homelab_dashboard/node_profiles.py` to add display aliases.
Use `HOSTNAME_ALIASES` alongside it for alternate raw spellings; the router's
`ringoM4-wifi` and `ringoA20` resolve to `ringo-M4` and `ringo-A20` respectively.
The case-insensitive map is shared by node cards, topology, guest cards/search, and
DHCP devices; raw hostnames and IDs stay unchanged. The Japanese entries render as
hiragana while preserving the `-M4` and `-A20` suffixes. Future aliases do not create
placeholder nodes; they apply when a node or lease is discovered.

The LAN Devices and Guest / IoT panels below Nodes read dnsmasq's default `/tmp/dhcp.leases` over SSH
through `/api/devices`. It shows hostname, IPv4 address, and uppercase MAC addresses,
without read timestamps or expiry dates. Expiry stays internal for filtering. It polls the
local cache every 10 seconds; Refresh forces both sources independently. Router errors
retain unexpired last-known leases with an explicit stale/error indication and do not
block PVE status. Leases are not proof of current connectivity. IPv6, static-IP device
discovery, and Wi-Fi association data are not implemented yet.

Leases in `192.168.0.0/16` appear in LAN Devices; all other IPv4 leases appear in
Guest / IoT. The API returns LAN first, then the remaining devices, sorting each
group by numeric IP address. This is a display grouping, not a connectivity or VLAN claim.

Before leases can load, verify the router's SSH host-key fingerprint against its
console or another trusted channel, then trust it in this machine's `known_hosts` and
configure SSH key authentication. For example, inspect a candidate ED25519 fingerprint
with `ssh-keyscan -t ed25519 192.168.10.1 | ssh-keygen -lf -`; this network scan alone
does not establish trust. Only after independently confirming it, connect with
`ssh root@192.168.10.1` to accept the verified key. The application never disables
host-key checking or handles passwords. No router trust changes have been performed.

## Layout

```text
project/
├── app.py                      entry point
├── server.py                   static files + /api/status
├── web/                        index.html, aero.css, aero.js (type-checked with JSDoc)
└── homelab_dashboard/
    ├── models.py               frozen, typed Node / Guest / ClusterSnapshot
    ├── config.py               settings from the environment
    └── sources/
        ├── base.py             StatusSource protocol and safe error type
        ├── pve_parser.py       pure Proxmox JSON -> models
        └── proxmox_ssh.py      SSH transport
```

## Test

```bash
python3 -m pytest project/tests
python3 -m mypy --strict project/server.py project/homelab_dashboard
```

## Hardware details

Each online node is probed for its CPU model and SMBIOS memory-array error correction
using `dmidecode --type 16`. Missing tools, insufficient permissions, and unknown firmware
values yield an unknown ECC reading, not a negative one. A firmware ECC report is not
proof that ECC is enabled or correcting errors; kernel EDAC data is needed for that.
With multiple memory arrays, a positive result means at least one reports ECC.

Memory descriptions in `homelab_dashboard/node_profiles.py` are explicitly configured:
Kex and Kveikur use DDR4 ECC RDIMMs; Cerulean uses one 32 GB DDR4 SODIMM.
Offline nodes retain configured inventory without claiming live readings. CPU fallbacks
remain italicized with an explanatory tooltip. GPU display and collection are disabled.

## Roadmap

### PVE features worth surfacing

Prioritize storage/pool usage and health, last successful backup and failed backup jobs,
cluster quorum, recent failed tasks, and small CPU/RAM history charts. Then consider
guest tags/notes, uptime, network/disk throughput, and version/update status. Link to PVE
for consoles, migrations, snapshots, backup configuration, and power controls rather
than rebuilding those management workflows. Use scoped PVE API tokens with PVEAuditor
where practical; host hardware inspection still needs a separate restricted probe.

### Inventory and natural language

Keep the first version read-only: discover nodes/guests, persist physical components,
locations and notes, then answer inventory questions. This is a coherent companion to
the dashboard; rebuilding PVE administration and adding autonomous infrastructure
changes would make the initial scope too wide.

For a single-user homelab, use FastAPI, SQLite (WAL), SQLAlchemy, and Alembic migrations.
Keep PVE and router collectors separate from inventory CRUD and serve cached observations
rather than doing SSH inside each request. Move to PostgreSQL only when concurrency or
deployment needs justify it.

Store assets with stable internal IDs, components linked to assets, network interfaces
with MAC addresses, source identifiers, timestamped observations, and an audit trail.
Do not identify devices by IP or hostname alone. Store PVE guest IDs with cluster identity.
Distinguish observed facts from manual assertions, including provenance, last seen,
collection failures, and conflicts; discovery must not overwrite manual notes silently.
Keep telemetry retention separate from long-lived inventory.

Natural language should call narrow, validated tools such as `search_assets`,
`get_asset`, and `list_components`, not execute generated SQL or shell commands. Return
answers with the relevant assets, source, and observation time. Add edits later through
validated change proposals, explicit confirmation, transactions, and audit records.
Treat discovered hostnames/notes as untrusted data, not model instructions. A vector
database is unnecessary for structured inventory; SQLite search is enough initially.

### Further OpenWRT discovery

The DHCPv4 collector targets `root@192.168.10.1` through SSH with key authentication,
verified host keys, an 8-second timeout, and a 60-second independent cache. For richer discovery,
Use `ubus -v list` to discover the router's actual methods: availability depends on its
OpenWRT version and installed packages. Prefer structured `ubus` JSON and `ip -j neigh`
where supported; the default BusyBox `ip` may need an `ip-full` installation for JSON.

On suitable installations, `ubus call dhcp ipv4leases` / `ipv6leases` expose leases;
otherwise parse dnsmasq's `/tmp/dhcp.leases` with its documented fields. Wi-Fi association
data can come from each `hostapd.*` object's `get_clients` method when available.
Join by MAC/interface and retain lease expiry and observation timestamps. DHCP leases
are not proof that a client is currently connected, neighbors are not a complete wired
client census, and static-IP devices may have no lease. Show leases and observed clients
as distinct states. Router outages should stale only this card, not the PVE dashboard.
Keep MAC/IP inventories local and credentials off the browser. Replace unrestricted
root access with a restricted read-only wrapper or scoped RPC permissions before exposing
the service beyond localhost. The live collector has successfully read DHCPv4 leases;
no SSH trust changes were performed by the application.

### Deferred GPU work

- [ ] Restore discovered GPU inventory only after verifying the installed hardware;
    do not reintroduce expected GPU entries in the dashboard.
- [ ] Restore host utilization/VRAM readings for AMD, NVIDIA, and Intel with separate
    caching and bounded probe costs. Existing probe helpers are retained but unused.
- [ ] Distinguish host-visible, driverless, and VFIO-passthrough cards; collect guest
    telemetry separately when the host cannot read a passed-through GPU.
- [ ] Track GPUs as inventory components with provenance and last-seen timestamps.
- [ ] Add per-DIMM discovery (`dmidecode --type 17`) and EDAC ECC enablement/error
    evidence, keeping configured specifications distinct from live verification.
