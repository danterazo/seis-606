// @ts-check

/**
 * @typedef {{ cpu_ratio: number | null, cpu_cores: number | null, memory_used_bytes: number | null, memory_total_bytes: number | null }} Resources
 * @typedef {"running" | "stopped" | "paused" | "unknown"} GuestState
 * @typedef {{ vmid: number, name: string, display_name?: string, node: string, kind: "vm" | "container", state: GuestState, resources: Resources }} Guest
 * @typedef {{ cpu_model: string | null, cpu_cores: number | null, cpu_threads: number | null, ecc_supported?: boolean | null, zfs_arc_bytes?: number | null, zfs_arc_max_bytes?: number | null, storage?: StorageHealth | null, hardware_errors?: HardwareErrors | null, source: "live" | "expected" | "unknown" }} Hardware
 * @typedef {{ timestamp: string, boot_id: string, source: string, message: string }} RawEvent
 * @typedef {{ category: "ecc_memory" | "cpu_mce" | "page_offline" | "pcie" | "storage_path", classification: "corrected" | "uncorrected" | "unspecified", title: string, level: HealthLevel, count: number, first_seen: string, last_seen: string, last_hour: number, last_day: number, boot_id: string, current_boot: boolean, boots_seen: number, recurrence: string[], fields: [string, string][], raw: RawEvent[] }} ErrorIncident
 * @typedef {{ boot_id: string, first_seen: string | null, last_seen: string | null, current: boolean }} BootRecord
 * @typedef {{ controller: string, label: string | null, corrected: number, uncorrected: number }} MemoryCounter
 * @typedef {{ level: HealthLevel, findings: string[], incidents: ErrorIncident[], boots: BootRecord[], memory_counters: MemoryCounter[], edac_available: boolean, journal_available: boolean, persisted_corrected: number | null, persisted_uncorrected: number | null, persisted_mce: number | null, boot_id: string | null, boot_started: string | null, collected_at: string | null, stale: boolean, error: string | null, last_success: string | null, counters_reset: boolean }} HardwareErrors
 * @typedef {"ok" | "warning" | "critical" | "unknown"} HealthLevel
 * @typedef {{ device: string, model: string | null, serial: string | null, kind: string, level: HealthLevel, standby: boolean, temperature_celsius: number | null, power_on_hours: number | null, findings: string[] }} Disk
 * @typedef {{ name: string, state: string, level: HealthLevel, capacity_percent: number | null, size_bytes: number | null, allocated_bytes: number | null, free_bytes: number | null, fragmentation_percent: number | null, layout: string | null, scan: string | null, findings: string[] }} Pool
 * @typedef {{ disks: Disk[], pools: Pool[], smart_available: boolean, zfs_available: boolean }} StorageHealth
 * @typedef {{ name: string, display_name: string, state: "online" | "offline" | "unknown", address: string | null, image: string | null, initial: string, color: string, memory_description?: string | null, memory_ecc?: boolean | null, resources: Resources, guests: Guest[], hardware: Hardware }} PveNode
 * @typedef {{ source: string, fetched_at: string, nodes: PveNode[] }} Snapshot
 * @typedef {"all" | "running" | "vm" | "container"} GuestFilter
 * @typedef {{ snapshot: Snapshot | null, error: string | null, selectedNode: string | null, filter: GuestFilter, query: string }} ViewState
 * @typedef {{ className?: string, text?: string, attrs?: Readonly<Record<string, string>> }} ElementOptions
 * @typedef {{ address: string, mac: string, hostname: string | null, display_name: string, network_group: "lan" | "guest_iot", expires_at: string | null }} DhcpLease
 * @typedef {{ source: string, router: string, fetched_at: string | null, stale: boolean, error: string | null, leases: DhcpLease[] }} DevicesSnapshot
 * @typedef {{ pending: boolean, message: string, error: boolean, retryAt: number }} GuestActionState
 * @typedef {{ timestamp: string, method: string, path: string, status: number, client: string }} ActivityLogEntry
 */

const STATUS_URL = "/api/status";
const DEVICES_URL = "/api/devices";
const REBOOT_URL = "/api/guests/reboot";
const LOGS_URL = "/api/logs";
const CLEAR_LOGS_URL = "/api/logs/clear";
const DEVICES_INTERVAL_MS = 10_000;
const REFRESH_INTERVAL_MS = 1_000;
const MAX_TOPOLOGY_GUESTS = 12;
const TOPOLOGY_NAME_LIMIT = 22;
const BYTES_PER_MIB = 1024 ** 2;
const BYTES_PER_GIB = 1024 ** 3;
const SVG_NS = "http://www.w3.org/2000/svg";

/** @type {ReadonlyArray<ReadonlyArray<string>>} */
const HEADER_HAIKUS = [
  ["I turn off the rack", "There is nothing left to fix", "I have found my peace"],
  ["I watch the lights blink", "I don't know what they tell me", "They blink anyway"],
  ["I cannot connect", "It was always DNS", "There goes my evening"],
];

/** @type {ViewState} */
const state = { snapshot: null, error: null, selectedNode: null, filter: "all", query: "" };
/** @type {DevicesSnapshot | null} */
let devicesSnapshot = null;
/** @type {string | null} */
let devicesError = null;
let devicesRefreshInFlight = false;
/** @type {Map<number, GuestActionState>} */
const guestActions = new Map();

/** @type {ReadonlyArray<{ id: GuestFilter, label: string }>} */
const FILTERS = [
  { id: "all", label: "All" },
  { id: "running", label: "Running" },
  { id: "vm", label: "VMs" },
  { id: "container", label: "LXCs" },
];

/**
 * @param {string} selector
 * @returns {HTMLElement}
 */
function required(selector) {
  const element = document.querySelector(selector);
  if (!(element instanceof HTMLElement)) throw new Error(`Missing element ${selector}`);
  return element;
}

/**
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag
 * @param {ElementOptions} [options]
 * @param {ReadonlyArray<Node | string>} [children]
 * @returns {HTMLElementTagNameMap[K]}
 */
function el(tag, options = {}, children = []) {
  const element = document.createElement(tag);
  if (options.className) element.className = options.className;
  if (options.text !== undefined) element.textContent = options.text;
  for (const [name, value] of Object.entries(options.attrs ?? {})) element.setAttribute(name, value);
  element.append(...children);
  return element;
}

/**
 * @param {string} tag
 * @param {Readonly<Record<string, string | number>>} [attrs]
 * @param {ReadonlyArray<Node | string>} [children]
 * @returns {SVGElement}
 */
function svg(tag, attrs = {}, children = []) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) element.setAttribute(name, String(value));
  element.append(...children);
  return element;
}

/** @param {number} value */
const clamp = (value) => Math.min(100, Math.max(0, value));

/** @param {Resources} resources @returns {number | null} */
function cpuPercent(resources) {
  return resources.cpu_ratio === null ? null : clamp(resources.cpu_ratio * 100);
}

/** @param {Resources} resources @returns {number | null} */
function memoryPercent({ memory_used_bytes: used, memory_total_bytes: total }) {
  return used === null || total === null || total <= 0 ? null : clamp((used / total) * 100);
}

/** @param {number | null} value */
const formatPercent = (value) => (value === null ? "—" : `${Math.round(value)}%`);

/** @param {string} text @param {number} limit */
const truncate = (text, limit) => (text.length > limit ? `${text.slice(0, limit - 1)}…` : text);

/** @param {number} value @param {number} digits */
const trimNumber = (value, digits) => value.toFixed(digits).replace(/\.0+$/, "");

/** Memory under 1 GB reads better in MB. */
/** @param {number} total @returns {{ size: number, label: string, digits: number }} */
const memoryUnit = (total) => (total < BYTES_PER_GIB ? { size: BYTES_PER_MIB, label: "MB", digits: 0 } : { size: BYTES_PER_GIB, label: "GB", digits: 1 });

/** @param {number} bytes */
function formatBytes(bytes) {
  const unit = memoryUnit(bytes);
  return `${trimNumber(bytes / unit.size, unit.digits)} ${unit.label}`;
}

/** Pool sizes run to terabytes. @param {number | null} bytes */
function formatPoolBytes(bytes) {
  if (bytes === null) return "—";
  return bytes >= BYTES_PER_GIB * 1024 ? `${trimNumber(bytes / (BYTES_PER_GIB * 1024), 2)} TB` : formatBytes(bytes);
}

/** @param {Pool} pool */
function poolUsage(pool) {
  return pool.allocated_bytes === null || pool.size_bytes === null ? null : `${formatPoolBytes(pool.allocated_bytes)} / ${formatPoolBytes(pool.size_bytes)}`;
}

/** @param {{ used: number, total: number }} args */
function formatMemoryPair({ used, total }) {
  const unit = memoryUnit(total);
  const usedUnit = memoryUnit(used);
  let usedText = trimNumber(used / usedUnit.size, usedUnit.digits);
  // A small but real reading should not be shown as zero.
  if (usedText === "0" && used > 0) usedText = trimNumber(used / usedUnit.size, 2);
  if (usedUnit.label !== unit.label) usedText += ` ${usedUnit.label}`;
  return `${usedText} / ${trimNumber(total / unit.size, unit.digits)} ${unit.label}`;
}

/** @param {Resources} resources */
const formatCores = ({ cpu_cores: cores }) => (cores === null ? "cores unknown" : `${cores} ${cores === 1 ? "Core" : "Cores"}`);

/** Allotment, usage, then percentage: "3/8 GB (38%)". @param {Resources} resources */
function formatRam(resources) {
  const { memory_used_bytes: used, memory_total_bytes: total } = resources;
  if (total === null) return "unknown";
  if (used === null) return `${formatBytes(total)} total`;
  return `${formatMemoryPair({ used, total })} (${formatPercent(memoryPercent(resources))})`;
}

/** @typedef {{ percent: number | null, text: string }} GuestMetric */

/** Stopped guests have nothing live to show, so they get no metrics at all. @param {Guest} guest @returns {{ cpu: GuestMetric, ram: GuestMetric } | null} */
function guestMetrics(guest) {
  if (guest.state !== "running") return null;
  const { resources } = guest;
  return {
    cpu: { percent: cpuPercent(resources), text: `${formatPercent(cpuPercent(resources))} · ${formatCores(resources)}` },
    ram: { percent: memoryPercent(resources), text: formatRam(resources) },
  };
}

/** @param {Guest} guest */
function guestTooltip(guest) {
  const header = `${guestLabel(guest)} (ID ${guest.vmid}) – ${guest.state}`;
  const metrics = guestMetrics(guest);
  return metrics === null ? header : `${header}\nCPU ${metrics.cpu.text}\nRAM ${metrics.ram.text}`;
}

/** @param {PveNode} node @param {Guest["kind"]} kind */
const countKind = (node, kind) => node.guests.filter((guest) => guest.kind === kind).length;

/** @param {number} count @param {string} noun */
const plural = (count, noun) => `${count} ${noun}${count === 1 ? "" : "s"}`;

/** @param {PveNode} node */
const guestSummary = (node) => `${plural(countKind(node, "vm"), "VM")} · ${plural(countKind(node, "container"), "LXC")}`;

const NODE_COLOR_PATTERN = /^#[0-9a-f]{6}$/i;
const FALLBACK_NODE_COLOR = "#5b6b7a";

/** The color is injected into a style attribute, so only plain hex values pass. @param {string | undefined} color */
const safeColor = (color) => (color !== undefined && NODE_COLOR_PATTERN.test(color) ? color : FALLBACK_NODE_COLOR);

/** @param {string | undefined} color */
const colorStyle = (color) => `--node-color: ${safeColor(color)}`;

/** @param {string} nodeName */
const colorOfNode = (nodeName) => safeColor(state.snapshot?.nodes.find((node) => node.name === nodeName)?.color);

/** @param {string} nodeName */
const initialOfNode = (nodeName) => state.snapshot?.nodes.find((node) => node.name === nodeName)?.initial || nodeName.charAt(0).toUpperCase();

/** @param {Guest["kind"]} kind */
const kindLabel = (kind) => (kind === "vm" ? "VM" : "LXC");

/** Capitalized name for display; the raw name stays the identifier. @param {PveNode} node */
const nodeLabel = (node) => node.display_name || node.name;

/** @param {Guest} guest */
const guestLabel = (guest) => guest.display_name || guest.name;

/** @param {string} nodeName */
const displayNodeName = (nodeName) => {
  const node = state.snapshot?.nodes.find((candidate) => candidate.name === nodeName);
  return node === undefined ? nodeName : nodeLabel(node);
};

/** @param {string} state */
const stateLabel = (state) => state.charAt(0).toUpperCase() + state.slice(1);

/** @param {string} state @param {string} label */
function statePill(state, label = stateLabel(state)) {
  return el("span", { className: `pill pill-${state}` }, [el("i", { className: "orb", attrs: { "aria-hidden": "true" } }), label]);
}

/** Percent of total memory held by ZFS ARC, capped at what is in use; Proxmox counts ARC as used, not cached. @param {PveNode} node @returns {number | null} */
function arcPercent(node) {
  const { memory_used_bytes: used, memory_total_bytes: total } = node.resources;
  const arc = node.hardware.zfs_arc_bytes;
  if (arc == null || used === null || total === null || total <= 0) return null;
  return clamp((Math.min(arc, used) / total) * 100);
}

/** @param {{ label: string, value: number | null, tone: "cpu" | "memory", arcValue?: number | null, title?: string }} args */
function gauge({ label, value, tone, arcValue = null, title }) {
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  /** @param {string} cls @param {number | null} percent */
  const ringArc = (cls, percent) =>
    svg("circle", {
      class: cls,
      cx: 28,
      cy: 28,
      r: radius,
      "stroke-dasharray": `${(circumference * (percent ?? 0)) / 100} ${circumference}`,
      transform: "rotate(-90 28 28)",
    });
  // The ARC arc sits underneath and spans all used memory; the green arc covers the non-ARC part.
  const arcs = arcValue === null || value === null ? [ringArc(`gauge-arc gauge-${tone}`, value)] : [ringArc("gauge-arc gauge-arc-zfs", value), ringArc(`gauge-arc gauge-${tone}`, value - arcValue)];
  const ring = svg("svg", { viewBox: "0 0 56 56", "aria-hidden": "true" }, [svg("circle", { class: "gauge-track", cx: 28, cy: 28, r: radius }), ...arcs]);
  return el("div", { className: "gauge", attrs: title ? { title } : {} }, [ring, el("span", { className: "gauge-value", text: formatPercent(value) }), el("span", { className: "gauge-label", text: label })]);
}

/** @param {{ label: string, metric: GuestMetric, tone: "cpu" | "memory" }} args */
function metricRow({ label, metric, tone }) {
  const fill = el("span", { className: `bar-fill bar-${tone}` });
  fill.style.width = `${metric.percent ?? 0}%`;
  return el("div", { className: "metric" }, [
    el("div", { className: "metric-head" }, [el("span", { className: "metric-label", text: label }), el("span", { text: metric.text })]),
    el("span", { className: "bar-track slim" }, [fill]),
  ]);
}

function renderBanner() {
  const banner = required("#banner");
  const { snapshot, error } = state;
  /** @type {{ tone: string, title: string, detail: string }} */
  let content;
  if (error !== null) {
    const lastGood = snapshot === null ? "" : ` Showing the last data from ${new Date(snapshot.fetched_at).toLocaleTimeString()}.`;
    content = { tone: "alert", title: "Can't Reach Proxmox", detail: `${error}${lastGood}` };
  } else if (snapshot === null) {
    content = { tone: "pending", title: "Connecting…", detail: "Asking Proxmox for the current status." };
  } else if (snapshot.nodes.length === 0) {
    content = { tone: "pending", title: "No Nodes Reported", detail: "Proxmox returned an empty cluster." };
  } else {
    const down = snapshot.nodes.filter((node) => node.state !== "online").length;
    content =
      down === 0
        ? { tone: "ok", title: "All Systems Operational", detail: `${plural(snapshot.nodes.length, "node")} online` }
        : { tone: "warn", title: `${down} of ${plural(snapshot.nodes.length, "Node")} Unavailable!`, detail: "Check the node list for details." };
  }
  banner.className = `banner banner-${content.tone}`;
  banner.replaceChildren(el("i", { className: "banner-icon", attrs: { "aria-hidden": "true" } }), el("strong", { text: content.title }), el("span", { text: content.detail }));
}

/** @param {PveNode} node */
function nodeAvatar(node) {
  if (!node.image) return el("span", { className: "server-glyph", attrs: { "aria-hidden": "true" } });
  return el("img", { className: "node-avatar", attrs: { src: node.image, alt: "", width: "48", height: "48", loading: "lazy" } });
}

/** @param {PveNode[]} nodes */
function renderNodeList(nodes) {
  const items = nodes.map((node) => {
    const button = el("button", { className: `node-row row-${node.state}`, attrs: { type: "button", style: colorStyle(node.color), "data-node": node.name, "aria-pressed": String(state.selectedNode === node.name) } }, [
      nodeAvatar(node),
      el("span", { className: "node-meta" }, [el("strong", { text: nodeLabel(node) }), statePill(node.state), el("small", { text: node.address ?? "Address unknown" })]),
    ]);
    return button;
  });
  required("#node-list").replaceChildren(...(items.length ? items : [el("p", { className: "empty", text: "No nodes to show." })]));
}

/** @param {string} label @param {string} value */
const fact = (label, value) => el("div", { className: "fact" }, [el("span", { className: "fact-label", text: label }), el("span", { className: "fact-value", text: value })]);

/** CPU topology is polled and cached with the per-node hardware probe. @param {Hardware} hardware */
function cpuModelLine({ cpu_model: model, cpu_cores: cores, cpu_threads: threads, source }) {
  const expected = source !== "live";
  const displayModel = model?.replace("Ryzen Threadripper PRO", "Threadripper").replace("Ryzen Threadripper", "Threadripper") ?? "CPU";
  const topology = `${cores ?? "?"}c/${threads ?? "?"}t`;
  const title = `${model ?? "CPU model unknown"} · ${cores ?? "Unknown"} cores / ${threads ?? "Unknown"} threads · ${expected ? "Expected hardware (CPU stats unavailable)" : "Read from the node"}`;
  return el("small", { className: `cpu-model${expected ? " is-expected" : ""}`, text: `${displayModel} (${topology})`, attrs: { title } });
}

/** @type {ReadonlyArray<HealthLevel>} */
const HEALTH_ORDER = ["ok", "unknown", "warning", "critical"];

/** @param {ReadonlyArray<HealthLevel>} levels @returns {HealthLevel} */
const worstLevel = (levels) => levels.reduce((worst, level) => (HEALTH_ORDER.indexOf(level) > HEALTH_ORDER.indexOf(worst) ? level : worst), /** @type {HealthLevel} */ ("ok"));

/** A badge that opens the node's storage details; a span because tiles are buttons and can't nest one. @param {string} nodeName @param {HealthLevel | "na"} level @param {string} text @param {string} title */
function healthBadge(nodeName, level, text, title) {
  return el("span", { className: `health-badge health-${level}`, text, attrs: { role: "button", tabindex: "0", title: `${title}\nClick for details`, "data-storage-node": nodeName } });
}

/** One SMART badge plus one badge per zpool, each coloured by its worst finding. @param {PveNode} node */
function storageBadges(node) {
  const storage = node.hardware.storage;
  if (!storage) return [];
  /** @type {HTMLElement[]} */
  const badges = [];
  if (!storage.smart_available) {
    badges.push(healthBadge(node.name, "na", "SMART N/A", "smartctl is not installed on this node"));
  } else if (storage.disks.length > 0) {
    const level = worstLevel(storage.disks.map((disk) => disk.level));
    const flagged = storage.disks.filter((disk) => disk.level !== "ok");
    const hottest = Math.max(...storage.disks.map((disk) => disk.temperature_celsius ?? -Infinity));
    const text = flagged.length === 0 ? "SMART OK" : `SMART ${flagged.length} ${level === "unknown" ? "UNREADABLE" : level === "warning" ? "WARN" : "CRITICAL"}`;
    const lines = flagged.length === 0 ? [`All ${plural(storage.disks.length, "disk")} healthy${Number.isFinite(hottest) ? `, Hottest ${hottest} °C` : ""}`] : flagged.map((disk) => `${disk.device}: ${disk.findings.join("; ")}`);
    // Warnings and criticals both go red so a flagged disk stands out.
    badges.push(healthBadge(node.name, level === "warning" ? "critical" : level, text, lines.join("\n")));
  }
  if (storage.zfs_available) {
    for (const pool of storage.pools) {
      const reason = (pool.state !== "ONLINE" ? pool.state : pool.findings[0] ?? pool.state).toUpperCase();
      const usage = poolUsage(pool);
      const headline = pool.level === "ok" ? `${pool.name} ${pool.state}` : `${pool.name} ${reason}${pool.findings.length > 1 ? ` +${pool.findings.length - 1}` : ""}`;
      // Only tank carries the extra stats on its badge for now.
      const extras = pool.name === "tank" ? [pool.fragmentation_percent === null ? null : `${pool.fragmentation_percent}% Frag`, pool.free_bytes === null ? null : `${formatPoolBytes(pool.free_bytes)} Free`, pool.scan].filter(Boolean) : [];
      const text = [headline, ...extras].join(" · ");
      const details = [usage === null ? null : `Used: ${usage}`, pool.fragmentation_percent === null ? null : `${pool.fragmentation_percent}% Fragmented`, pool.layout, pool.scan === null ? null : `Last Scan: ${pool.scan}`].filter(Boolean);
      badges.push(healthBadge(node.name, pool.level, text, [pool.findings.length === 0 ? `${pool.name} is healthy${pool.capacity_percent === null ? "" : `, ${pool.capacity_percent}% Full`}` : `${pool.name}: ${pool.findings.join("; ")}`, ...details].join("\n")));
    }
  }
  return badges.length === 0 ? [] : [el("div", { className: "storage-badges" }, badges)];
}

/** One badge for hardware error evidence, kept apart from the CPU and RAM utilization gauges. @param {PveNode} node */
function hardwareErrorBadges(node) {
  const errors = node.hardware.hardware_errors;
  if (!errors) return [];
  const current = errors.incidents.filter((incident) => incident.current_boot && incident.level !== "ok");
  const history = errors.incidents.filter((incident) => !incident.current_boot).length;
  const headline = errors.level === "unknown" ? "HW Errors N/A" : errors.level === "ok" ? "HW Errors: None" : current.length > 0 ? `HW Errors: ${plural(current.length, "Incident")}` : errors.incidents.length === 0 ? "HW Errors: Counters" : `HW Errors: ${plural(history, "Past Incident")}`;
  const staleness = errors.stale ? " · Stale" : "";
  const lines = [errors.findings.length === 0 ? "No hardware errors reported since the last check" : errors.findings.join("\n"), errors.stale ? errors.error ?? "Data is stale" : null].filter(Boolean);
  const badge = healthBadge(node.name, errors.level, headline + staleness, lines.join("\n"));
  badge.removeAttribute("data-storage-node");
  badge.setAttribute("data-hwerrors-node", node.name);
  return [el("div", { className: "storage-badges" }, [badge])];
}

/** @param {string | null} iso */
const formatTime = (iso) => (iso === null ? "—" : new Date(iso).toLocaleString());

/** @param {ErrorIncident["category"]} category */
const categoryLabel = (category) => ({ ecc_memory: "ECC memory", cpu_mce: "CPU machine check", page_offline: "Page soft-offline", pcie: "PCIe", storage_path: "Storage path" })[category];

/** Hardware errors, boots and currently flagged storage in one time-ordered list; nothing here asserts a cause. @param {PveNode} node @param {HardwareErrors} errors */
function timelineEntries(node, errors) {
  /** @type {{ time: string | null, label: string, detail: string, level: HealthLevel | "info", historical: boolean }[]} */
  const entries = [];
  for (const boot of errors.boots) {
    entries.push({ time: boot.first_seen, label: "Boot started (uptime reset)", detail: boot.current ? "Current boot" : "Earlier boot", level: "info", historical: !boot.current });
  }
  for (const incident of errors.incidents) {
    entries.push({ time: incident.first_seen, label: `${categoryLabel(incident.category)}: ${incident.title}`, detail: `${plural(incident.count, "event")}, last ${formatTime(incident.last_seen)}`, level: incident.level, historical: !incident.current_boot });
  }
  const storage = node.hardware.storage;
  const flagged = [...(storage?.disks ?? []), ...(storage?.pools ?? [])].filter((item) => item.level !== "ok");
  for (const item of flagged) {
    const name = "device" in item ? item.device : item.name;
    entries.push({ time: errors.collected_at, label: `Storage currently flagged: ${name}`, detail: item.findings.join("; "), level: item.level, historical: false });
  }
  return entries.sort((a, b) => (b.time ?? "").localeCompare(a.time ?? ""));
}

/** @param {PveNode} node */
function renderHardwareErrorsDialog(node) {
  const errors = node.hardware.hardware_errors;
  required("#hwerrors-heading").textContent = `Hardware Errors · ${nodeLabel(node)}`;
  if (!errors) {
    required("#hwerrors-body").replaceChildren(el("p", { className: "empty", text: "Hardware errors are not monitored for this node." }));
    return;
  }
  /** @param {HealthLevel} level @param {string} text */
  const levelCell = (level, text) => el("span", { className: `health-badge health-${level}`, text });
  /** @param {string[]} headers @param {HTMLElement[]} rows @param {string} empty */
  const table = (headers, rows, empty) =>
    rows.length === 0 ? el("p", { className: "empty", text: empty }) : el("table", { className: "storage-table" }, [el("thead", {}, [el("tr", {}, headers.map((header) => el("th", { text: header })))]), el("tbody", {}, rows)]);
  const monitoring = [
    errors.stale ? `Stale: ${errors.error ?? "no recent reading"}. Last successful check ${formatTime(errors.last_success)}.` : `Checked ${formatTime(errors.collected_at)}.`,
    errors.boot_started === null ? null : `Current boot began ${formatTime(errors.boot_started)}; counters since boot restart from zero at each reboot.`,
    errors.counters_reset ? "A reboot was observed, so since-boot counters were reset; earlier events come from the journal and rasdaemon history." : null,
    errors.edac_available ? null : "EDAC counters are not available on this node.",
    errors.journal_available ? null : "The kernel journal could not be read.",
  ].filter(Boolean);
  const persisted = errors.persisted_corrected === null ? "rasdaemon is not installed or has no history" : `${errors.persisted_corrected} corrected / ${errors.persisted_uncorrected ?? 0} uncorrected${errors.persisted_mce === null ? "" : `, ${errors.persisted_mce} MCE records`}`;
  const counterRows = errors.memory_counters.map((counter) =>
    el("tr", {}, [
      el("td", {}, [el("code", { text: counter.label ?? counter.controller })]),
      el("td", { text: String(counter.corrected) }),
      el("td", { text: String(counter.uncorrected) }),
    ]),
  );
  const incidentRows = errors.incidents.map((incident) =>
    el("tr", { className: incident.current_boot ? "" : "is-historical" }, [
      el("td", {}, [levelCell(incident.level, incident.current_boot ? "This boot" : "Earlier boot")]),
      el("td", { text: `${categoryLabel(incident.category)} · ${incident.classification}` }),
      el("td", {}, [
        el("div", { text: incident.title }),
        el("small", { text: [...incident.recurrence, ...incident.fields.map(([name, value]) => `${name}=${value}`)].join(" · ") }),
        el("details", {}, [el("summary", { text: `Raw records (latest ${incident.raw.length} of ${incident.count})` }), el("pre", { className: "raw-events", text: incident.raw.map((raw) => `${raw.timestamp} boot ${raw.boot_id.slice(0, 8)} ${raw.source}: ${raw.message}`).join("\n") })]),
      ]),
      el("td", { text: `${incident.count} (${incident.last_hour} in 1 h, ${incident.last_day} in 24 h)` }),
      el("td", { text: formatTime(incident.first_seen) }),
      el("td", { text: formatTime(incident.last_seen) }),
    ]),
  );
  const timelineRows = timelineEntries(node, errors).map((entry) =>
    el("tr", { className: entry.historical ? "is-historical" : "" }, [
      el("td", { text: formatTime(entry.time) }),
      el("td", {}, [entry.level === "info" ? el("span", { className: "health-badge health-na", text: "Info" }) : levelCell(entry.level, stateLabel(entry.level))]),
      el("td", { text: entry.historical ? "Earlier boot" : "Current" }),
      el("td", { text: entry.label }),
      el("td", {}, [el("small", { text: entry.detail })]),
    ]),
  );
  required("#hwerrors-body").replaceChildren(
    el("p", { className: "hw-status", text: monitoring.join(" ") }),
    el("h3", { text: "Findings" }),
    errors.findings.length === 0 ? el("p", { className: "empty", text: "No hardware errors reported." }) : el("ul", { className: "hw-findings" }, errors.findings.map((finding) => el("li", { text: finding }))),
    el("h3", { text: "ECC Counters" }),
    el("p", { className: "hw-status", text: `Persisted history (survives reboots): ${persisted}` }),
    table(["DIMM / Controller (since boot)", "Corrected", "Uncorrected"], counterRows, "No EDAC counters on this node."),
    el("h3", { text: "Incidents" }),
    table(["Scope", "Class", "Evidence", "Events", "First seen", "Last seen"], incidentRows, errors.journal_available ? "No hardware error events in the last 14 days." : "Event history unavailable."),
    el("h3", { text: "Timeline" }),
    el("p", { className: "hw-status", text: "Entries are listed together by time only; being close in time does not mean one caused another." }),
    table(["Time", "Level", "Scope", "Event", "Detail"], timelineRows, "Nothing to show."),
    el("p", { className: "hw-status", text: "This view only reads. Offlining CPUs, rebooting, clearing counters, or running scrubs and stress tests are manual operator actions." }),
  );
}

/** @type {string | null} */
let hwErrorsDialogNode = null;
let hwErrorsRendered = "";

/** @param {string | null} nodeName */
function openHardwareErrorsDialog(nodeName) {
  hwErrorsDialogNode = nodeName;
  syncHardwareErrorsDialog();
}

/** Keeps an open dialog current as new snapshots arrive. */
function syncHardwareErrorsDialog() {
  const dialog = required("#hwerrors-dialog");
  if (!(dialog instanceof HTMLDialogElement) || hwErrorsDialogNode === null) return;
  const node = state.snapshot?.nodes.find((candidate) => candidate.name === hwErrorsDialogNode);
  if (node === undefined) {
    dialog.close();
    return;
  }
  // Re-rendering would collapse any raw-record sections the user has open.
  const signature = JSON.stringify([node.hardware.hardware_errors, node.hardware.storage]);
  if (dialog.open && signature === hwErrorsRendered) return;
  hwErrorsRendered = signature;
  renderHardwareErrorsDialog(node);
  if (!dialog.open) dialog.showModal();
}

/** @param {PveNode} node */
function renderStorageDialog(node) {
  const storage = node.hardware.storage;
  required("#storage-heading").textContent = `Storage Health · ${nodeLabel(node)}`;
  /** @param {HealthLevel} level @param {string} text */
  const levelCell = (level, text) => el("span", { className: `health-badge health-${level}`, text });
  /** @param {number | null} powerOnHours */
  const diskAge = (powerOnHours) => {
    if (powerOnHours === null) return "—";
    const days = Math.round(powerOnHours / 24);
    return days > 365 ? `${Math.floor(days / 365)}y ${days % 365}d` : `${days} d`;
  };
  const diskRows = (storage?.disks ?? []).map((disk) =>
    el("tr", {}, [
      el("td", {}, [levelCell(disk.level, disk.standby ? "Standby" : stateLabel(disk.level === "ok" ? "OK" : disk.level))]),
      el("td", {}, [el("code", { text: disk.device })]),
      el("td", {}, [el("small", { text: disk.model ?? "" })]),
      el("td", {}, [el("small", { text: disk.serial ?? "" })]),
      el("td", { text: disk.kind.toUpperCase() }),
      el("td", { text: disk.temperature_celsius === null ? "—" : `${disk.temperature_celsius} °C` }),
      el("td", { text: diskAge(disk.power_on_hours) }),
      el("td", { text: disk.findings.length === 0 ? "Normal" : disk.findings.join("; ") }),
    ]),
  );
  const poolRows = (storage?.pools ?? []).map((pool) =>
    el("tr", {}, [
      el("td", {}, [levelCell(pool.level, pool.state)]),
      el("td", {}, [el("code", { text: pool.name })]),
      el("td", { text: pool.capacity_percent === null ? "—" : `${pool.capacity_percent}% Full` }),
      el("td", { text: poolUsage(pool) ?? "—" }),
      el("td", { text: formatPoolBytes(pool.free_bytes) }),
      el("td", { text: pool.fragmentation_percent === null ? "—" : `${pool.fragmentation_percent}%` }),
      el("td", {}, [el("small", { text: pool.layout ?? "—" })]),
      el("td", {}, [el("small", { text: pool.scan ?? "—" })]),
      el("td", { text: pool.findings.length === 0 ? "Normal" : pool.findings.join("; ") }),
    ]),
  );
  /** @param {string[]} headers @param {HTMLElement[]} rows @param {string} empty */
  const table = (headers, rows, empty) =>
    rows.length === 0 ? el("p", { className: "empty", text: empty }) : el("table", { className: "storage-table" }, [el("thead", {}, [el("tr", {}, headers.map((header) => el("th", { text: header })))]), el("tbody", {}, rows)]);
  required("#storage-body").replaceChildren(
    el("h3", { text: "Disks (SMART)" }),
    table(["Status", "Device", "Model", "Serial #", "Type", "Temp", "Age", "Findings"], diskRows, storage?.smart_available ? "No disks reported." : "smartctl is not installed on this node."),
    el("h3", { text: "ZFS Pools" }),
    table(["Status", "Pool", "Capacity", "Used / Size", "Free", "Frag", "Layout", "Last Scan", "Findings"], poolRows, storage?.zfs_available ? "No pools reported." : "ZFS tools are not installed on this node."),
  );
}

/** @type {string | null} */
let storageDialogNode = null;

/** @param {string | null} nodeName */
function openStorageDialog(nodeName) {
  storageDialogNode = nodeName;
  syncStorageDialog();
}

/** Keeps an open dialog current as new snapshots arrive. */
function syncStorageDialog() {
  const dialog = required("#storage-dialog");
  if (!(dialog instanceof HTMLDialogElement) || storageDialogNode === null) return;
  const node = state.snapshot?.nodes.find((candidate) => candidate.name === storageDialogNode);
  if (node === undefined) {
    dialog.close();
    return;
  }
  renderStorageDialog(node);
  if (!dialog.open) dialog.showModal();
}

/** Memory and error badges share the first row, storage badges the second, so a longer badge never reshuffles the rest. @param {HTMLElement[]} hardware @param {HTMLElement[]} storage */
function footerRows(hardware, storage) {
  const rows = [hardware, storage].filter((row) => row.length > 0).map((row) => el("div", { className: "footer-row" }, row));
  return el("div", { className: "tile-footer" }, rows);
}

/** @param {PveNode[]} nodes */
function renderOverview(nodes) {
  const tiles = nodes.map((node) => {
    const online = node.state === "online";
    const arcBytes = node.hardware.zfs_arc_bytes ?? null;
    const arcMax = node.hardware.zfs_arc_max_bytes ?? null;
    const ramTitle = arcBytes === null ? undefined : `ZFS ARC (amber): ${formatBytes(arcBytes)}`;
    const gauges = [gauge({ label: "CPU", value: cpuPercent(node.resources), tone: "cpu" }), gauge({ label: "RAM", value: memoryPercent(node.resources), tone: "memory", arcValue: arcPercent(node), title: ramTitle })];
    const modelLine = cpuModelLine(node.hardware);
    const { memory_used_bytes: used, memory_total_bytes: total } = node.resources;
    const memoryText = used !== null && total !== null ? formatMemoryPair({ used, total }) : formatRam(node.resources);
    const hardwareDetails =
      node.memory_ecc == null && !node.memory_description
        ? []
        : [el("div", { className: "memory-details" }, [el("span", {
            className: `memory-ecc ${node.memory_ecc ? "ecc-memory" : "non-ecc-memory"}`,
            text: [node.memory_description, node.memory_ecc == null ? null : node.memory_ecc ? "ECC" : "Non-ECC"].filter(Boolean).join(" "),
            attrs: { title: node.memory_ecc ? "Configured ECC memory; active error correction is not verified" : "Configured memory" },
          })])];
    return el("button", { className: `tile tile-${node.state}`, attrs: { type: "button", style: colorStyle(node.color), "data-node": node.name, "aria-pressed": String(state.selectedNode === node.name) } }, [
      el("span", { className: "tile-head" }, [
        el("span", { className: "server-glyph", attrs: { "aria-hidden": "true" } }),
        el("span", { className: "tile-title" }, [el("strong", { text: nodeLabel(node) }), ...(modelLine ? [modelLine] : []), el("small", { text: guestSummary(node) })]),
        statePill(node.state),
      ]),
      ...(online
        ? [el("div", { className: "tile-readings" }, [
            el("div", { className: "gauges" }, gauges),
            el("div", { className: "tile-details" }, [el("div", { className: "facts" }, [fact("RAM", memoryText), ...(arcBytes === null ? [] : [fact("ZFS ARC", arcMax ? formatMemoryPair({ used: arcBytes, total: arcMax }) : formatBytes(arcBytes))])])]),
          ]), footerRows([...hardwareDetails, ...hardwareErrorBadges(node)], storageBadges(node))]
        : [el("p", { className: "offline-note", text: "No live readings." }), ...hardwareDetails, footerRows(hardwareErrorBadges(node), [])]),
    ]);
  });
  const host = required("#overview");
  const columnCount = Math.max(1, Math.min(tiles.length, Math.floor((host.clientWidth + 12) / 292)));
  const columns = Array.from({ length: columnCount }, () => el("div", { className: "tile-column" }));
  tiles.forEach((tile, index) => columns[index % columnCount].append(tile));
  host.replaceChildren(...(tiles.length ? columns : [el("p", { className: "empty", text: "Nothing to show yet." })]));
}

/**
 * @param {{ x: number, y: number, text: string, className: string, anchor?: "start" | "middle" }} args
 */
function svgText({ x, y, text, className, anchor = "middle" }) {
  return svg("text", { x, y, class: className, "text-anchor": anchor }, [text]);
}

/** @param {PveNode[]} nodes */
function renderTopology(nodes) {
  const host = required("#topology");
  if (nodes.length === 0) {
    host.replaceChildren(el("p", { className: "empty", text: "No nodes to draw." }));
    return;
  }
  const column = 244;
  const pill = { width: 214, height: 30, gap: 7, badge: 42, stripe: 6 };
  const width = Math.max(520, nodes.length * column);
  const hub = { x: width / 2, y: 42 };
  const nodeY = 150;
  const guestTop = 238;
  const tallest = Math.max(...nodes.map((node) => Math.min(node.guests.length, MAX_TOPOLOGY_GUESTS)));
  const height = guestTop + Math.max(1, tallest) * (pill.height + pill.gap) + 34;

  /** @type {SVGElement[]} */
  const drawing = [
    svg("defs", {}, [svg("clipPath", { id: "topo-badge-clip" }, [svg("rect", { width: pill.badge, height: pill.height, rx: pill.height / 2 })])]),
  ];
  drawing.push(svg("circle", { class: "topo-hub", cx: hub.x, cy: hub.y, r: 22 }), svgText({ x: hub.x, y: hub.y - 28, text: "Cluster", className: "topo-label" }));

  nodes.forEach((node, index) => {
    const x = (width / nodes.length) * (index + 0.5);
    const offline = node.state !== "online";
    const mid = (hub.y + nodeY) / 2;
    drawing.push(svg("path", { class: `topo-link${offline ? " is-down" : ""}`, style: colorStyle(node.color), d: `M ${hub.x} ${hub.y + 22} C ${hub.x} ${mid}, ${x} ${mid}, ${x} ${nodeY - 28}` }));

    drawing.push(
      svg("g", { class: `topo-node${offline ? " is-down" : ""}${state.selectedNode === node.name ? " is-selected" : ""}`, style: colorStyle(node.color), "data-node": node.name }, [
        svg("rect", { class: "topo-node-body", x: x - 38, y: nodeY - 28, width: 76, height: 56, rx: 10 }),
        svg("rect", { class: "topo-node-slot", x: x - 28, y: nodeY - 18, width: 56, height: 9, rx: 4 }),
        svg("rect", { class: "topo-node-slot", x: x - 28, y: nodeY - 4, width: 56, height: 9, rx: 4 }),
        svg("circle", { class: "topo-node-led", cx: x + 22, cy: nodeY + 17, r: 3.5 }),
      ]),
      svgText({ x, y: nodeY + 46, text: nodeLabel(node), className: "topo-label" }),
      svgText({ x, y: nodeY + 62, text: node.address ?? "address unknown", className: "topo-sub" }),
    );

    const shown = node.guests.slice(0, MAX_TOPOLOGY_GUESTS);
    shown.forEach((guest, guestIndex) => {
      const gx = x - pill.width / 2;
      const gy = guestTop + guestIndex * (pill.height + pill.gap);
      const kind = guest.kind === "vm" ? "vm" : "lxc";
      const dim = offline || guest.state !== "running";
      drawing.push(
        svg("g", { class: `topo-guest topo-${kind}${dim ? " is-dim" : ""}`, style: colorStyle(node.color) }, [
          svg("title", {}, [guestTooltip(guest)]),
          svg("rect", { class: "topo-pill", x: gx, y: gy, width: pill.width, height: pill.height, rx: 15 }),
          svg("g", { transform: `translate(${gx} ${gy})`, "clip-path": "url(#topo-badge-clip)" }, [
            svg("rect", { class: "topo-badge", width: pill.badge, height: pill.height }),
            svg("rect", { class: "topo-stripe", y: pill.height - pill.stripe, width: pill.badge, height: pill.stripe }),
          ]),
          svgText({ x: gx + pill.badge / 2, y: gy + 17.5, text: kindLabel(guest.kind), className: "topo-guest-kind" }),
          svgText({ x: gx + pill.badge + 8, y: gy + 19.5, text: truncate(guestLabel(guest), TOPOLOGY_NAME_LIMIT), className: "topo-guest-name", anchor: "start" }),
          svg("circle", { class: "topo-led", cx: gx + pill.width - 14, cy: gy + pill.height / 2, r: 4 }),
        ]),
      );
    });
    if (node.guests.length > shown.length) {
      drawing.push(svgText({ x, y: guestTop + shown.length * (pill.height + pill.gap) + 10, text: `+${node.guests.length - shown.length} more`, className: "topo-sub" }));
    }
  });

  host.replaceChildren(svg("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Cluster topology" }, drawing));
}

/** @type {Readonly<Record<GuestState, number>>} */
const STATE_RANK = { running: 0, paused: 1, stopped: 2, unknown: 3 };

/** Running guests first, then paused, stopped, unknown; the cluster-unique VM id orders each group. @param {Guest} a @param {Guest} b */
const compareGuests = (a, b) => STATE_RANK[a.state] - STATE_RANK[b.state] || a.vmid - b.vmid;

/** @param {Guest} guest @param {GuestFilter} filter */
function matchesFilter(guest, filter) {
  return filter === "all" || (filter === "running" ? guest.state === "running" : guest.kind === filter);
}

/** @param {PveNode[]} nodes @returns {Guest[]} */
function visibleGuests(nodes) {
  const query = state.query.trim().toLowerCase();
  return nodes
    .filter((node) => state.selectedNode === null || node.name === state.selectedNode)
    .flatMap((node) => node.guests)
    .filter((guest) => matchesFilter(guest, state.filter))
    .filter((guest) => query === "" || `${guest.name} ${guestLabel(guest)} ${guest.vmid} ${guest.node} ${displayNodeName(guest.node)}`.toLowerCase().includes(query))
    .sort(compareGuests);
}

/** @param {PveNode[]} nodes */
function renderGuests(nodes) {
  required("#guests-title").textContent = state.selectedNode === null ? "VMs & Containers" : `VMs & Containers on ${displayNodeName(state.selectedNode)}`;
  required("#node-chips").replaceChildren(
    el("button", { className: "chip", text: "All Nodes", attrs: { type: "button", "data-node-filter": "", "aria-pressed": String(state.selectedNode === null) } }),
    ...nodes.map((node) =>
      el("button", { className: "chip", attrs: { type: "button", style: colorStyle(node.color), "data-node-filter": node.name, "aria-pressed": String(state.selectedNode === node.name) } }, [
        el("i", { className: "chip-dot", attrs: { "aria-hidden": "true" } }),
        nodeLabel(node),
      ]),
    ),
  );
  required("#chips").replaceChildren(
    ...FILTERS.map(({ id, label }) => el("button", { className: "chip", text: label, attrs: { type: "button", "data-filter": id, "aria-pressed": String(state.filter === id) } })),
  );

  const guests = visibleGuests(nodes);
  const rows = guests.map((guest) => {
    const metrics = guestMetrics(guest);
    const action = guestActions.get(guest.vmid);
    const rebootButton = el("button", {
      className: `guest-reboot${action?.pending ? " is-loading" : ""}`,
      attrs: {
        type: "button", "data-reboot-vmid": String(guest.vmid), "data-reboot-node": guest.node,
        title: `Reboot ${guestLabel(guest)} (ID ${guest.vmid}) on ${displayNodeName(guest.node)}`,
        "aria-label": `Reboot ${guestLabel(guest)} (ID ${guest.vmid})`,
      },
    }, [el("span", { className: "refresh-icon", text: "↻", attrs: { "aria-hidden": "true" } })]);
    rebootButton.disabled = guest.state !== "running" || nodes.find((node) => node.name === guest.node)?.state !== "online" || Boolean(action?.pending) || (action?.retryAt ?? 0) > Date.now();
    return el("li", { className: "guest", attrs: { style: colorStyle(colorOfNode(guest.node)) } }, [
      el("span", { className: "guest-mark", attrs: { "aria-hidden": "true" } }, [
        el("span", { className: `guest-icon guest-${guest.kind}`, text: kindLabel(guest.kind) }),
        el("span", { className: "guest-badge", text: initialOfNode(guest.node) }),
      ]),
      el("div", { className: "guest-body" }, [
        el("div", { className: "guest-header" }, [
          el("strong", { className: "guest-name", text: guestLabel(guest), attrs: { title: guestLabel(guest) } }),
          el("div", { className: "guest-state-actions" }, [rebootButton, statePill(guest.state)]),
        ]),
        el("div", { className: "guest-sub" }, [el("small", { text: `${displayNodeName(guest.node)} · ID ${guest.vmid}` })]),
        ...(metrics === null ? [] : [el("div", { className: "guest-metrics" }, [metricRow({ label: "CPU", metric: metrics.cpu, tone: "cpu" }), metricRow({ label: "RAM", metric: metrics.ram, tone: "memory" })])]),
        ...(action ? [el("small", { className: `guest-action-status${action.error ? " is-error" : ""}`, text: action.message, attrs: { role: "status" } })] : []),
      ]),
    ]);
  });
  const empty = nodes.length === 0 ? "No VMs or containers to show." : "No VMs or containers match this view.";
  required("#guest-list").replaceChildren(...(rows.length ? rows : [el("li", { className: "empty", text: empty })]));
}

/** @param {number} vmid @param {string} nodeName */
async function rebootGuest(vmid, nodeName) {
  const existing = guestActions.get(vmid);
  if (existing?.pending || (existing?.retryAt ?? 0) > Date.now()) return;
  const node = state.snapshot?.nodes.find((candidate) => candidate.name === nodeName);
  const guest = node?.guests.find((candidate) => candidate.vmid === vmid);
  if (!guest || node?.state !== "online" || guest.state !== "running") return;
  if (!window.confirm(`Reboot ${guestLabel(guest)} (ID ${vmid}) on ${nodeLabel(node)}?\nThis interrupts services running in this ${kindLabel(guest.kind)}.`)) return;
  guestActions.set(vmid, { pending: true, message: "Submitting reboot…", error: false, retryAt: 0 });
  renderGuests(state.snapshot?.nodes ?? []);
  try {
    const response = await fetch(REBOOT_URL, {
      method: "POST", headers: { "Content-Type": "application/json", "X-Homelab-Action": "reboot" },
      body: JSON.stringify({ vmid, node: nodeName }),
    });
    /** @type {unknown} */
    const payload = await response.json();
    if (!response.ok) throw new Error(errorMessage(payload));
    guestActions.set(vmid, { pending: false, message: "Reboot command submitted.", error: false, retryAt: Date.now() + 30_000 });
    void refresh({ force: true });
  } catch (error) {
    guestActions.set(vmid, { pending: false, message: error instanceof Error ? error.message : "Reboot failed.", error: true, retryAt: Date.now() + 30_000 });
  } finally {
    renderGuests(state.snapshot?.nodes ?? []);
    window.setTimeout(() => renderGuests(state.snapshot?.nodes ?? []), 30_000);
  }
}

function renderDevices() {
  const error = devicesError ?? devicesSnapshot?.error;
  const stale = devicesSnapshot?.stale || error != null;
  for (const { group, prefix } of [{ group: "lan", prefix: "lan" }, { group: "guest_iot", prefix: "guest-iot" }]) {
    const status = required(`#${prefix}-devices-status`);
    status.classList.toggle("is-stale", Boolean(stale));
    status.textContent = error
      ? `${error}${devicesSnapshot?.fetched_at ? " Showing last-known leases." : ""}`
      : devicesSnapshot === null ? "Loading DHCP leases…" : `${devicesSnapshot.source} · ${devicesSnapshot.router}`;
    const leases = (devicesSnapshot?.leases ?? []).filter((lease) => lease.network_group === group && typeof lease.address === "string");
    const rows = leases.map((lease) => el("li", { className: "device" }, [
      el("div", { className: "device-title" }, [
        el("strong", { text: lease.display_name, attrs: { title: lease.hostname ?? "Unnamed device" } }),
      ]),
      el("dl", { className: "device-fields" }, [
        el("dt", { className: "device-field-label", text: "IPv4" }),
        el("dd", { className: "device-address", text: lease.address ?? "Not reported" }),
        el("dt", { className: "device-field-label", text: "MAC" }),
        el("dd", { className: "device-mac", text: lease.mac?.toUpperCase() ?? "Not reported" }),
      ]),
    ]));
    required(`#${prefix}-device-list`).replaceChildren(...(rows.length ? rows : [el("li", { className: "empty", text: error ? "Devices unavailable." : devicesSnapshot === null ? "" : "No devices reported." })]));
  }
}

/** @param {{ force?: boolean }} [options] */
async function refreshDevices({ force = false } = {}) {
  if (devicesRefreshInFlight) return;
  devicesRefreshInFlight = true;
  try {
    const response = await fetch(force ? `${DEVICES_URL}?refresh=1` : DEVICES_URL, { cache: "no-store" });
    /** @type {unknown} */
    const payload = await response.json();
    if (!response.ok) throw new Error(errorMessage(payload));
    devicesSnapshot = /** @type {DevicesSnapshot} */ (payload);
    devicesError = null;
  } catch (error) {
    devicesError = error instanceof Error ? error.message : "DHCP leases are unavailable.";
  } finally {
    devicesRefreshInFlight = false;
    renderDevices();
  }
}

async function loadActivityLog() {
  const status = required("#logs-status");
  status.textContent = "Loading…";
  try {
    const response = await fetch(LOGS_URL, { cache: "no-store" });
    /** @type {unknown} */
    const payload = await response.json();
    if (!response.ok) throw new Error(errorMessage(payload));
    const entries = payload && typeof payload === "object" && "entries" in payload && Array.isArray(payload.entries)
      ? /** @type {ActivityLogEntry[]} */ (payload.entries)
      : [];
    const rows = entries.map((entry) => el("li", { className: "log-entry" }, [
      el("span", { className: `log-status log-status-${Math.floor(entry.status / 100)}`, text: String(entry.status) }),
      el("div", { className: "log-detail" }, [
        el("code", { className: "log-path", text: `${entry.method} ${entry.path}` }),
        el("span", { className: "log-meta", text: `${new Date(entry.timestamp).toLocaleString()} · ${entry.client}` }),
      ]),
    ]));
    required("#logs-list").replaceChildren(...rows);
    status.textContent = `${entries.length} ${entries.length === 1 ? "record" : "records"} · newest 500`;
  } catch (error) {
    required("#logs-list").replaceChildren();
    status.textContent = error instanceof Error ? error.message : "Activity log is unavailable.";
  }
}

async function clearActivityLog() {
  if (!window.confirm("Clear the activity log? This cannot be undone.")) return;
  const button = required("#clear-logs-button");
  button.setAttribute("disabled", "");
  try {
    const response = await fetch(CLEAR_LOGS_URL, {
      method: "POST",
      headers: { "X-Homelab-Action": "clear-logs" },
    });
    /** @type {unknown} */
    const payload = await response.json();
    if (!response.ok) throw new Error(errorMessage(payload));
    await loadActivityLog();
  } catch (error) {
    required("#logs-status").textContent = error instanceof Error ? error.message : "Could not clear the activity log.";
  } finally {
    button.removeAttribute("disabled");
  }
}

function render() {
  const nodes = state.snapshot?.nodes ?? [];
  renderBanner();
  renderNodeList(nodes);
  renderOverview(nodes);
  renderTopology(nodes);
  renderGuests(nodes);
  syncStorageDialog();
  syncHardwareErrorsDialog();
  required("#source-label").textContent = state.snapshot?.source ?? "No data source connected";
  const lastUpdate = state.snapshot ? new Date(state.snapshot.fetched_at).toLocaleTimeString() : null;
  required("#updated").textContent =
    state.error !== null ? (lastUpdate === null ? "Update failed" : `Update failed · data from ${lastUpdate}`) : lastUpdate === null ? "Connecting…" : `Updated ${lastUpdate}`;
}

/** @param {unknown} payload */
function errorMessage(payload) {
  return typeof payload === "object" && payload !== null && "error" in payload && typeof payload.error === "string" ? payload.error : "Status is unavailable.";
}

let refreshInFlight = false;

/** Polls the local server, which shares one Proxmox query between callers; redraws only when something changed. @param {{ force?: boolean }} [options] */
async function refresh({ force = false } = {}) {
  if (refreshInFlight) return;
  refreshInFlight = true;
  const button = required("#refresh-button");
  if (force) {
    button.setAttribute("disabled", "");
    button.classList.add("is-loading");
  }
  let changed = true;
  try {
    const response = await fetch(force ? `${STATUS_URL}?refresh=1` : STATUS_URL, { cache: "no-store" });
    /** @type {unknown} */
    const payload = await response.json();
    if (!response.ok) throw new Error(errorMessage(payload));
    const snapshot = /** @type {Snapshot} */ (payload);
    changed = state.error !== null || state.snapshot === null || state.snapshot.fetched_at !== snapshot.fetched_at;
    state.snapshot = snapshot;
    state.error = null;
    if (state.selectedNode !== null && !snapshot.nodes.some((node) => node.name === state.selectedNode)) state.selectedNode = null;
  } catch (error) {
    // Keep the last good snapshot on screen; a single failed poll shouldn't blank the page.
    const message = error instanceof Error ? error.message : "Status is unavailable.";
    changed = state.error !== message;
    state.error = message;
  } finally {
    refreshInFlight = false;
    button.removeAttribute("disabled");
    button.classList.remove("is-loading");
    if (changed || force) render();
  }
}

/** @param {string} name */
function toggleNode(name) {
  state.selectedNode = state.selectedNode === name ? null : name;
  render();
}

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const rebootTarget = event.target.closest("[data-reboot-vmid]");
  if (rebootTarget instanceof HTMLButtonElement && !rebootTarget.disabled) {
    void rebootGuest(Number(rebootTarget.getAttribute("data-reboot-vmid")), rebootTarget.getAttribute("data-reboot-node") ?? "");
    return;
  }
  const hwErrorsBadge = event.target.closest("[data-hwerrors-node]");
  if (hwErrorsBadge instanceof Element) {
    openHardwareErrorsDialog(hwErrorsBadge.getAttribute("data-hwerrors-node"));
    return;
  }
  const storageBadge = event.target.closest("[data-storage-node]");
  if (storageBadge instanceof Element) {
    openStorageDialog(storageBadge.getAttribute("data-storage-node"));
    return;
  }
  const nodeChip = event.target.closest("[data-node-filter]");
  if (nodeChip instanceof Element) {
    state.selectedNode = nodeChip.getAttribute("data-node-filter") || null;
    render();
    return;
  }
  const nodeTarget = event.target.closest("[data-node]");
  if (nodeTarget instanceof Element && nodeTarget.getAttribute("data-node")) {
    toggleNode(nodeTarget.getAttribute("data-node") ?? "");
    return;
  }
  const chip = event.target.closest("[data-filter]");
  if (chip instanceof Element) {
    state.filter = /** @type {GuestFilter} */ (chip.getAttribute("data-filter"));
    render();
  }
});

required("#search").addEventListener("input", (event) => {
  state.query = event.target instanceof HTMLInputElement ? event.target.value : "";
  renderGuests(state.snapshot?.nodes ?? []);
});
required("#refresh-button").addEventListener("click", () => {
  void refresh({ force: true });
  void refreshDevices({ force: true });
});
required("#logs-button").addEventListener("click", () => {
  const dialog = required("#logs-dialog");
  if (dialog instanceof HTMLDialogElement) dialog.showModal();
  void loadActivityLog();
});
required("#close-logs-button").addEventListener("click", () => {
  const dialog = required("#logs-dialog");
  if (dialog instanceof HTMLDialogElement) dialog.close();
});
required("#clear-logs-button").addEventListener("click", () => void clearActivityLog());
required("#close-storage-button").addEventListener("click", () => {
  const dialog = required("#storage-dialog");
  if (dialog instanceof HTMLDialogElement) dialog.close();
});
required("#storage-dialog").addEventListener("close", () => {
  storageDialogNode = null;
});
required("#close-hwerrors-button").addEventListener("click", () => {
  const dialog = required("#hwerrors-dialog");
  if (dialog instanceof HTMLDialogElement) dialog.close();
});
required("#hwerrors-dialog").addEventListener("close", () => {
  hwErrorsDialogNode = null;
});
document.addEventListener("keydown", (event) => {
  if ((event.key !== "Enter" && event.key !== " ") || !(event.target instanceof Element)) return;
  const hwErrorsBadge = event.target.closest("[data-hwerrors-node]");
  if (hwErrorsBadge instanceof Element) {
    event.preventDefault();
    openHardwareErrorsDialog(hwErrorsBadge.getAttribute("data-hwerrors-node"));
    return;
  }
  const storageBadge = event.target.closest("[data-storage-node]");
  if (!(storageBadge instanceof Element)) return;
  event.preventDefault();
  openStorageDialog(storageBadge.getAttribute("data-storage-node"));
});

const selectedHaiku = HEADER_HAIKUS[Math.floor(Math.random() * HEADER_HAIKUS.length)];
required("#haiku").replaceChildren(...selectedHaiku.map((line, index) => el("span", { text: index < selectedHaiku.length - 1 ? `${line} /` : line })));
const refreshSeconds = REFRESH_INTERVAL_MS / 1000;
required("#refresh-note").textContent = `Guest controls · checks for updates every ${refreshSeconds === 1 ? "second" : `${refreshSeconds} seconds`}`;
let overviewWidth = 0;
new ResizeObserver(([entry]) => {
  if (entry.contentRect.width === overviewWidth) return;
  overviewWidth = entry.contentRect.width;
  renderOverview(state.snapshot?.nodes ?? []);
}).observe(required("#overview"));
render();
renderDevices();
void refresh();
void refreshDevices();
window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
window.setInterval(() => void refreshDevices(), DEVICES_INTERVAL_MS);

// Dev only: swap stylesheets in place and reload for assets that need re-execution.
void (async () => {
  /** @returns {Promise<{version: string, assets: Record<string, number>} | null>} */
  const readVersion = async () => {
    try {
      const response = await fetch("/__dev/version", { cache: "no-store" });
      return response.ok ? await response.json() : null;
    } catch {
      return null;
    }
  };
  const initial = await readVersion();
  if (initial === null) return;
  let previous = initial;

  /** @param {string} path @param {number} version @returns {Promise<boolean>} */
  const replaceStylesheet = (path, version) => {
    const links = /** @type {HTMLLinkElement[]} */ ([...document.querySelectorAll('link[rel="stylesheet"]')])
      .filter((link) => new URL(link.href).pathname === path);
    if (links.length === 0) return Promise.resolve(true);

    return Promise.all(links.map((link) => new Promise((resolve) => {
      const replacement = /** @type {HTMLLinkElement} */ (link.cloneNode());
      const url = new URL(link.href);
      url.searchParams.set("__dev", String(version));
      replacement.href = url.toString();
      replacement.addEventListener("load", () => {
        link.remove();
        resolve(true);
      }, { once: true });
      replacement.addEventListener("error", () => {
        replacement.remove();
        resolve(false);
      }, { once: true });
      link.after(replacement);
    }))).then((results) => results.every(Boolean));
  };

  let checkInFlight = false;
  setInterval(async () => {
    if (checkInFlight) return;
    checkInFlight = true;
    try {
      const current = await readVersion();
      if (current === null) return;
      if (current.version !== previous.version) {
        location.reload();
        return;
      }

      const changedPaths = [...new Set([...Object.keys(previous.assets), ...Object.keys(current.assets)])]
        .filter((path) => previous.assets[path] !== current.assets[path]);
      if (changedPaths.length === 0) return;

      const requiresReload = changedPaths.some((path) => (
        !path.toLowerCase().endsWith(".css")
        || previous.assets[path] === undefined
        || current.assets[path] === undefined
      ));
      if (requiresReload) {
        location.reload();
        return;
      }

      for (const path of changedPaths) {
        const loaded = await replaceStylesheet(path, current.assets[path]);
        if (!loaded) {
          location.reload();
          return;
        }
      }
      previous = current;
    } finally {
      checkInFlight = false;
    }
  }, 1000);
})();
