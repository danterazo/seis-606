# Homelab Dashboard

A status dashboard with explicit guest reboot controls for a Proxmox VE cluster, styled after Frutiger Aero / Y2K desktops. Resource readings come
from Proxmox; display profiles, fallback CPU models, and memory descriptions are configured separately. SSH uses hostnames resolved by the local system.

## Run

```bash
python3 project/app.py
```

Open the printed URL (default `http://127.0.0.1:8765`). The server needs only the Python standard library and an OpenSSH client.

| Variable                          |       Default        | Purpose                                                                                                                                                                                                                                                                                                           |
| :-------------------------------- | :------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HOMELAB_PVE_SSH_HOST`            |     `cerulean`       | Host, IP, or SSH alias of any cluster node; the default hostname resolves according to this machine's local hosts/DNS configuration                                                                                                                                                                                |
| `HOMELAB_PVE_SSH_USER`            |        `root`        | Account used for every connection                                                                                                                                                                                                                                                                                 |
| `HOMELAB_SSH_TIMEOUT`             |         `15`         | Seconds to wait for Proxmox                                                                                                                                                                                                                                                                                       |
| `HOMELAB_CACHE_SECONDS`           |         `10`         | Minimum seconds between Proxmox queries (one costs ~2 CPU-seconds on a node); the page itself polls every second                                                                                                                                                                                                  |
| `HOMELAB_HARDWARE_CACHE_SECONDS`  |         `3`          | Minimum seconds between CPU/firmware ECC probes of each online node (a tiny read-only Python script sent over the same SSH connection settings; nothing is installed or written on the node)                                                                                                                      |
| `HOMELAB_ROUTER_SSH_HOST`         |       `flint`        | OpenWRT router for DHCPv4 leases; displayed as Flint2                                                                                                                                                                                                                                                              |
| `HOMELAB_STORAGE_CACHE_SECONDS`   |        `300`         | Minimum seconds between SMART / `zpool` reads of each online node, run in the background (needs `smartctl`; disks in standby are not woken). Thresholds live in `sources/storage_parser.py` (HDD warn 45 °C / critical 50 °C)                                                                                     |
| `HOMELAB_HW_ERRORS_CACHE_SECONDS` |        `120`         | Minimum seconds between hardware-error reads (EDAC counters, 14 days of kernel/rasdaemon journal, `ras-mc-ctl --summary`) of each online node, run in the background. Read-only; the last reading is kept and marked stale when a node is unreachable. Recurrence threshold lives in `sources/hwerrors_parser.py` |
| `HOMELAB_ROUTER_SSH_USER`         |        `root`        | Router SSH account (key authentication only)                                                                                                                                                                                                                                                                      |
| `HOMELAB_ROUTER_CACHE_SECONDS`    |         `60`         | Router lease cache TTL, including failures; independent of PVE                                                                                                                                                                                                                                                    |
| `HOMELAB_UI_HOST` / `PORT`        | `127.0.0.1` / `8765` | Where the dashboard listens                                                                                                                                                                                                                                                                                       |

### First Connection

Run `make init-ssh-trust` to check the cluster node hostnames and the configured router SSH host (`flint` by default):

```bash
make init-ssh-trust
```

The helper exits without prompting when all configured hostnames already have `known_hosts` entries. For each new host, OpenSSH displays its fingerprint
and asks you to confirm it; accepted host keys are written directly to `known_hosts`. Compare each fingerprint with the machine's console or another
trusted channel before accepting it. This does not create or modify SSH identity keys. Hostnames remain the same across machines, while local hosts/DNS
records can map them to LAN addresses on the desktop and Tailscale addresses on the laptop. Node IPs shown in the dashboard come from that same local
hostname resolution.

WSL does not import custom Windows hosts-file entries into its generated `/etc/hosts`. This WSL setup resolves `flint2` through Tailscale DNS to
`100.100.10.1`, despite the Windows hosts-file mapping to `192.168.10.1`. The dashboard defaults to the reachable LAN hostname `flint` instead;
both names display as Flint2 without changing the SSH destination. Override `HOMELAB_ROUTER_SSH_HOST` when a different route is needed.
To have WSL use the same per-machine mappings, change
`generateHosts=true` to `generateHosts=false` under `[network]` in `/etc/wsl.conf`, then run `wsl --shutdown` from Windows PowerShell. After reopening
the distro, link WSL's hosts file to Windows' file:

```bash
sudo cp -a /etc/hosts /etc/hosts.wsl-backup
sudo rm /etc/hosts
sudo ln -s /mnt/c/Windows/System32/drivers/etc/hosts /etc/hosts
getent ahostsv4 flint kex cerulean kveikur
```

The lookup should show the Windows-file addresses. Repeat with each machine's own Windows hosts file so the desktop and laptop resolve the same names
to their respective LAN or Tailscale IPs. WSL's DNS tunneling is already enabled by default in the installed WSL version; changing `.wslconfig` is not
needed for this hosts-file setup.

Connections use `root` by default. To use another account, set `HOMELAB_PVE_SSH_USER`; a non-root account needs the `PVEAuditor` role to read cluster
resources.

## Security

I have plenty of experience making apps accessible from the internet, but this app is deliberately not public: it would be a privacy nightmare. It has
no user login, and its read endpoints reveal detailed node and guest information, device names, DHCP leases, IP/MAC addresses, and request metadata.

The intended deployment is on my home network so any machine on my LAN can access it, through a local-only reverse proxy at
`https://dash.samskeyti.net`. The proxy, DNS, firewall, and router must keep that hostname and service unreachable from the public internet; do not
use port forwarding or a public tunnel. HTTPS protects data in transit, but does not add authentication: LAN clients can read the dashboard's status,
lease, and activity-log endpoints. Keep `HOMELAB_UI_HOST=127.0.0.1` for local development, and allow LAN clients to reach only the reverse proxy;
allow the app upstream to accept connections only from that proxy.

Guest start/reboot and log-clear requests are restricted to loopback clients with a matching localhost Host and Origin plus an app-specific action
header. These checks help prevent remote and cross-origin writes; they are not user authentication. Other processes or users on the same machine
should be treated as trusted with the dashboard.

SSH uses the WSL2 OpenSSH client at `/usr/bin/ssh` with public-key authentication only. Password and keyboard-interactive authentication are disabled, interactive
prompts are disabled, and strict host-key checking is enabled. This is an inherited security measure provided by OpenSSH, and my existing SSH config,
keys, and `known_hosts` file. The app does not handle SSH passwords. Independently verify each host-key fingerprint before trusting it, like I have
did when initially configuring these servers. **DON'T** commit private keys to this repository.

Other inherited security measures include the project's `.gitignore`, which excludes `.env`, `.env.*`, and `.streamlit/secrets.toml` to reduce the
chance of accidentally committing local secrets. Ignore rules do not protect files that are already tracked or secure secrets stored on disk; keep
credentials out of source control and protect them with appropriate local file permissions.

SSH commands run as `root` by default on both Proxmox and the router, so compromise of the dashboard process or its local account carriies superuser
privileges. I settled for this because PVE, by default, uses `root` as the primary user. If remote machines offer non-root accounts with sufficient
privileges, consider using them instead to reduce the risk associated with `root`.

### Guest Reboots

The round orange arrow beside each guest's status submits a reboot after confirmation. It is disabled for stopped guests, unavailable nodes, and
pending/recent submissions. The server refreshes cluster inventory, checks that the guest still belongs to the selected node, then runs exactly
`pct reboot <ID>` for an LXC or `qm reboot <ID>` for a VM over verified SSH to that node's reported address. IDs, kind, and destination are not
arbitrary commands supplied by the browser.

`POST /api/guests/reboot` accepts only a JSON guest ID and node name. Writes require a loopback client, localhost Host, matching Origin, and the
dashboard's action header; cross-origin forms and remote clients are rejected. This is a local tool, not an authenticated multi-user management
service. Do not expose it publicly. SSH runs as `HOMELAB_PVE_SSH_USER`; `PVEAuditor` alone does not grant shell reboot permissions. Use root or a
deliberately restricted command wrapper/account that can reboot guests.

Only one reboot submission runs at a time, and attempts for a guest have a 30-second cooldown. A timeout does not prove the reboot failed: check the
guest before retrying. Success means the command was submitted, not that the OS has finished rebooting. Polling and node/router discovery remain
read-only. Automated tests use fake SSH; browser action tests intercept requests and do not reboot real guests.

### Device Names and Leases

Edit `DISPLAY_NAMES` in `homelab_dashboard/node_profiles.py` to configure display names. This is the only naming map: the router's `ringoM4-wifi` and
`ringoA20` are matched directly to their hiragana display names. The hyphenated `ringo-A20` spelling is an alias for the same display name; no
intermediate alias resolution is used. The case-insensitive map is shared by node cards, topology, guest cards/search, and DHCP devices; raw hostnames
and IDs stay unchanged. The Japanese entries render as hiragana using the exact labels configured in the map. Future aliases do not create placeholder
nodes; they apply when a node or lease is discovered.

Cluster nodes are ordered numerically by their locally resolved IP address, with IPv4 before IPv6. Missing or invalid addresses sort last; names break
ties alphabetically. The node list, overview, topology, and node filters use this
ordering rather than a fixed profile rank. Online topology links use longer, thicker moving dashes; offline links remain static gray dashes. Motion
indicates node availability, not measured network traffic.

The LAN Devices and Guest / IoT panels below Nodes read `dnsmasq`'s default `/tmp/dhcp.leases` over SSH through `/api/devices`. Each panel identifies
the router by its configured SSH host (displayed as Flint2 for `flint`, due to it being a GL.iNet Flint 2) and OpenWrt release version. Unavailable router details appear in orange;
connection errors are available by hovering over the router line instead of repeating the failure beneath it. Cards show the name directly above
labeled IPv4 and uppercase MAC rows, with no redundant hostname heading. When a MAC prefix is registered, the server shows its IEEE-registered
manufacturer from the public OUI registry. The registry is downloaded and cached server-side; individual MAC addresses are not sent to a lookup
service. Locally administered/randomized MACs and unmatched prefixes have no manufacturer line, and registry/network failures do not block leases.
Only devices with IPv4 leases are listed; IPv6-only devices and addresses are omitted. The active collector does not query IPv6 leases or neighbors.
Standalone IPv6 parsing and correlation helpers remain tested
for potential future use but are not invoked. Read timestamps and expiry dates remain hidden. Expiry stays internal for filtering. It polls the local
cache every 10 seconds; Refresh forces both sources independently. Router errors retain unexpired last-known leases with an inline
`Showing last-known leases` status after the router/version, separated by a dot only when present. Manufacturer rows appear directly below MAC as
`Vendor`, with the same label in the tooltip and accessible name. Router errors retain an explicit stale/error
indication and do not block PVE status. Leases are not proof of current connectivity. Static-IPv4-only discovery and Wi-Fi association data are not
implemented yet.

Leases in `192.168.0.0/16` appear in LAN Devices; all other IPv4 leases appear in Guest / IoT. The API returns LAN first, then the remaining devices.
In both panels, named devices come before IP-only devices, with numeric IP ordering within each subgroup. This is a display grouping, not a
connectivity or VLAN claim.

Before leases can load, verify the router's SSH host-key fingerprint against its console or another trusted channel, then trust it in this machine's
`known_hosts` and configure SSH key authentication. For example, inspect a candidate ED25519 fingerprint with
`ssh-keyscan -t ed25519 flint | ssh-keygen -lf -`; this network scan alone does not establish trust. Only after independently confirming it,
connect with `ssh root@flint` to accept the verified key. The application never disables host-key checking, modifies `known_hosts`, or handles
passwords.

## Layout

| Directory                                                   | Purpose                                                                 |
| :---------------------------------------------------------- | :---------------------------------------------------------------------- |
| `project/`                                                  | Application entry points, project configuration, and documentation      |
| `project/.github/`                                          | Copilot guidance and spec-kit workflow skills                           |
| `project/.github/skills/`                                   | Spec-kit workflow instructions                                          |
| `project/.specify/`                                         | Spec-kit templates, workflows, and configuration                        |
| `project/.streamlit/`                                       | Streamlit configuration example                                         |
| `project/assets/`                                           | Dashboard artwork and visual assets                                     |
| `project/homelab_dashboard/`                                | Dashboard domain, configuration, presentation, and data collection code |
| `project/homelab_dashboard/services/`                       | Guest actions and node health services                                  |
| `project/homelab_dashboard/sources/`                        | Proxmox, router, hardware, storage, and error data sources              |
| `project/homelab_dashboard/ui/`                             | Dashboard HTML rendering                                                |
| `project/logs/`                                             | Runtime request logs                                                    |
| `project/reference/`                                        | Original project requirements and reference material                    |
| `project/scripts/`                                          | Project helper scripts                                                  |
| `project/specs/`                                            | Feature specifications, plans, contracts, and checklists                |
| `project/specs/001-homelab-inventory-dashboard/`            | Homelab dashboard feature design artifacts                              |
| `project/specs/001-homelab-inventory-dashboard/checklists/` | Requirements checklist for the dashboard feature                        |
| `project/specs/001-homelab-inventory-dashboard/contracts/`  | Data-source interface contracts                                         |
| `project/tests/`                                            | Automated tests and shared test fixtures                                |
| `project/tests/integration/`                                | End-to-end dashboard behavior tests                                     |
| `project/tests/unit/`                                       | Focused tests for dashboard modules                                     |
| `project/web/`                                              | Browser interface, styles, scripts, and frontend tooling                |
| `project/web/images/`                                       | Decorative and node-specific dashboard images                           |

## Test

```bash
python3 -m pytest project/tests
python3 -m mypy --strict project/server.py project/homelab_dashboard
```

## Hardware Details

Each online node is probed for its CPU model, physical-core/logical-thread counts from `/proc/cpuinfo`, and SMBIOS memory-array error correction using
`dmidecode --type 16`. CPU readings use the hardware-probe cache. Missing tools, insufficient permissions, and unknown firmware values yield an
unknown ECC reading, not a negative one. A firmware ECC report is not proof that ECC is enabled or correcting errors; kernel EDAC data is needed for
that. With multiple memory arrays, a positive result means at least one reports ECC.

Memory descriptions in `homelab_dashboard/node_profiles.py` are explicitly configured: Kex and Kveikur use DDR4 ECC RDIMMs; Cerulean uses one 32 GB
DDR4 SODIMM. The overview uses compact ECC / Non-ECC badges from the configured memory details, independently of whether the node is online. Firmware
ECC diagnostics remain available in hardware data but are not shown as a sentence in the cards. An ECC badge identifies configured memory; it does not
verify active error correction. Unconfigured nodes have no ECC badge rather than an assumed negative result. Offline nodes retain configured memory
details without claiming live readings. CPU fallbacks remain italicized with an explanatory tooltip. GPU display and collection are disabled.

## What's Next?

### Home-Network Deployment

- [ ] Host the dashboard in a dedicated LXC on the home network and make it reachable from LAN machines.
- [ ] Configure a LAN-only reverse proxy at `https://dash.samskeyti.net`; keep its DNS, firewall, and routing local, and prevent public ingress.
- [ ] Preserve the current loopback and origin protections for write requests. Decide how trusted proxy requests should work before enabling guest
      actions through the proxy.

### PVE Features Worth Surfacing

- [ ] Show storage and pool usage and health.
- [ ] Show the latest successful backup and recent failed backup or maintenance tasks.
- [ ] Surface cluster quorum and recent failed tasks.
- [ ] Collect bounded, cached CPU/RAM/storage samples and show short-window history charts.
- [ ] Consider guest tags and notes, uptime, network/disk throughput, and version/update status.
- [ ] Link to PVE for consoles, migrations, snapshots, backup configuration, and other power controls instead of rebuilding those management
      workflows.
- [ ] Use scoped PVE API tokens with PVEAuditor where practical; keep host hardware inspection on a separate restricted probe.

### Inventory and Natural Language

- Keep the first version read-only: discover nodes and guests, persist physical components, locations, and notes, then answer inventory questions.
- Use FastAPI, SQLite (WAL), SQLAlchemy, and Alembic migrations for the single-user homelab.
- Keep PVE and router collectors separate from inventory CRUD; serve cached observations rather than running SSH inside each request. Move to
  PostgreSQL only when concurrency or deployment needs justify it.
- Store assets with stable internal IDs, linked components, network interfaces with MAC addresses, source identifiers, timestamped observations, and
  an audit trail.
- Do not identify devices by IP or hostname alone; store PVE guest IDs with cluster identity.
- Distinguish observed facts from manual assertions with provenance, last-seen times, collection failures, and conflicts. Discovery must not silently
  overwrite manual notes.
- Keep telemetry retention separate from long-lived inventory.
- Use narrow, validated tools such as `search_assets`, `get_asset`, and `list_components`; never execute generated SQL or shell commands.
- Return answers with the relevant assets, source, and observation time. Add edits later through validated change proposals, explicit confirmation,
  transactions, and audit records.
- Treat discovered hostnames and notes as untrusted data, not model instructions. SQLite search is sufficient for structured inventory; a vector
  database is unnecessary initially.

### Chatbot Window

- [ ] Add a chatbot window for managing home inventory, asking questions about nodes, and describing tasks in natural language for execution on
      selected nodes.
- [ ] Connect through a server-side inference adapter. Start with LM Studio's OpenAI-compatible base URL `http://100.100.20.10:1234/v1`; keep the
      endpoint and model configurable so the inference server can move to Kveikur later.
- [ ] Give the chatbot validated inventory and node tools, not unrestricted generated SQL or shell access. Preview target nodes and proposed changes;
      require explicit confirmation for writes and disruptive actions, and audit each execution/result.
- [ ] Support streamed replies, conversation history, tool/task progress, cancellation, and clear endpoint-unavailable or execution-failed states.
      Start with inventory queries and node questions before enabling confirmed task execution.

### Further OpenWRT Discovery

- The DHCPv4 collector reads `root@flint` over SSH with key authentication, verified host keys, an 8-second timeout, and an independent
      60-second cache. It reads DHCPv4 leases when the configured router hostname is reachable.
- [ ] Inspect `ubus -v list` for methods supported by the router's OpenWRT version and packages.
- [ ] Prefer structured `ubus` JSON and `ip -j neigh` where available; BusyBox `ip` may need `ip-full` for JSON output.
- [ ] Read `ubus call dhcp ipv4leases` / `ipv6leases` where supported; otherwise parse `dnsmasq`'s `/tmp/dhcp.leases`.
- [ ] Read Wi-Fi associations from each `hostapd.*` object's `get_clients` method when available.
- [ ] Join lease and association data by MAC/interface and retain expiry and observation times.
- Keep DHCP leases distinct from current connectivity: neighbors are not a complete wired census, and static-IP devices may have no lease. Show leases
  and observed clients separately.
- Keep MAC/IP inventories local and credentials off the browser; router outages should stale only this card, not the PVE dashboard.
- [ ] Replace unrestricted root access with a restricted read-only wrapper or scoped RPC permissions before exposing the service beyond localhost.

### GPU and Hardware Follow-Up

- [ ] Restore discovered GPU inventory only after verifying the installed hardware; do not reintroduce expected GPU entries in the dashboard.
- [ ] Restore host utilization/VRAM readings for AMD, NVIDIA, and Intel with separate caching and bounded probe costs. Existing probe helpers are
      retained but unused.
- [ ] Distinguish host-visible, driverless, and VFIO-passthrough cards; collect guest telemetry separately when the host cannot read a passed-through
      GPU.
- [ ] Track GPUs as inventory components with provenance and last-seen timestamps.
- [ ] Add per-DIMM discovery (`dmidecode --type 17`) and EDAC ECC enablement/error evidence, keeping configured specifications distinct from live
      verification.
