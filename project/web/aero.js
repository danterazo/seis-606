// @ts-check

/**
 * @typedef {{ cpu_ratio: number | null, cpu_cores: number | null, memory_used_bytes: number | null, memory_total_bytes: number | null }} Resources
 * @typedef {"running" | "stopped" | "paused" | "unknown"} GuestState
 * @typedef {{ vmid: number, name: string, display_name?: string, node: string, kind: "vm" | "container", state: GuestState, resources: Resources }} Guest
 * @typedef {{ cpu_model: string | null, ecc_supported?: boolean | null, source: "live" | "expected" | "unknown" }} Hardware
 * @typedef {{ name: string, display_name: string, state: "online" | "offline" | "unknown", address: string | null, image: string | null, initial: string, color: string, memory_description?: string | null, resources: Resources, guests: Guest[], hardware: Hardware }} PveNode
 * @typedef {{ source: string, fetched_at: string, nodes: PveNode[] }} Snapshot
 * @typedef {"all" | "running" | "vm" | "container"} GuestFilter
 * @typedef {{ snapshot: Snapshot | null, error: string | null, selectedNode: string | null, filter: GuestFilter, query: string }} ViewState
 * @typedef {{ className?: string, text?: string, attrs?: Readonly<Record<string, string>> }} ElementOptions
 * @typedef {{ address: string, mac: string, hostname: string | null, display_name: string, expires_at: string | null }} DhcpLease
 * @typedef {{ source: string, router: string, fetched_at: string | null, stale: boolean, error: string | null, leases: DhcpLease[] }} DevicesSnapshot
 */

const STATUS_URL = "/api/status";
const DEVICES_URL = "/api/devices";
const DEVICES_INTERVAL_MS = 10_000;
const REFRESH_INTERVAL_MS = 1_000;
const MAX_TOPOLOGY_GUESTS = 12;
const TOPOLOGY_NAME_LIMIT = 22;
const BYTES_PER_MIB = 1024 ** 2;
const BYTES_PER_GIB = 1024 ** 3;
const SVG_NS = "http://www.w3.org/2000/svg";

/** @type {ViewState} */
const state = { snapshot: null, error: null, selectedNode: null, filter: "all", query: "" };
/** @type {DevicesSnapshot | null} */
let devicesSnapshot = null;
/** @type {string | null} */
let devicesError = null;
let devicesRefreshInFlight = false;

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
const formatCores = ({ cpu_cores: cores }) => (cores === null ? "cores unknown" : `${cores} ${cores === 1 ? "core" : "Cores"}`);

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

/** @param {{ label: string, value: number | null, tone: "cpu" | "memory" }} args */
function gauge({ label, value, tone }) {
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const arc = svg("circle", {
    class: `gauge-arc gauge-${tone}`,
    cx: 28,
    cy: 28,
    r: radius,
    "stroke-dasharray": `${(circumference * (value ?? 0)) / 100} ${circumference}`,
    transform: "rotate(-90 28 28)",
  });
  const ring = svg("svg", { viewBox: "0 0 56 56", "aria-hidden": "true" }, [svg("circle", { class: "gauge-track", cx: 28, cy: 28, r: radius }), arc]);
  return el("div", { className: "gauge" }, [ring, el("span", { className: "gauge-value", text: formatPercent(value) }), el("span", { className: "gauge-label", text: label })]);
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
        : { tone: "warn", title: `${down} of ${plural(snapshot.nodes.length, "Node")} Unavailable`, detail: "Check the node list for details." };
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

/** The CPU model is a quiet subtitle; italics mark it as configured rather than read from the node. @param {Hardware} hardware */
function cpuModelLine({ cpu_model: model, source }) {
  if (model === null) return null;
  const expected = source !== "live";
  return el("small", { className: `cpu-model${expected ? " is-expected" : ""}`, text: model, attrs: { title: expected ? "Expected hardware (node not probed)" : "Read from the node" } });
}

/** @param {PveNode[]} nodes */
function renderOverview(nodes) {
  const tiles = nodes.map((node) => {
    const online = node.state === "online";
    const gauges = [gauge({ label: "CPU", value: cpuPercent(node.resources), tone: "cpu" }), gauge({ label: "RAM", value: memoryPercent(node.resources), tone: "memory" })];
    const modelLine = cpuModelLine(node.hardware);
    const { memory_used_bytes: used, memory_total_bytes: total } = node.resources;
    const memoryText = used !== null && total !== null ? formatMemoryPair({ used, total }) : formatRam(node.resources);
    const hardwareDetails = [
      ...(node.memory_description ? [el("small", { className: "memory-description", text: node.memory_description, attrs: { title: "Configured memory inventory, not a live module reading" } })] : []),
      ...(node.hardware.ecc_supported == null ? [] : [el("small", { className: "ecc-description", text: `ECC: ${node.hardware.ecc_supported ? "Reported by firmware" : "Not reported by firmware"}`, attrs: { title: "SMBIOS memory-array error correction; not proof that ECC is enabled" } })]),
    ];
    return el("button", { className: `tile tile-${node.state}`, attrs: { type: "button", style: colorStyle(node.color), "data-node": node.name, "aria-pressed": String(state.selectedNode === node.name) } }, [
      el("span", { className: "tile-head" }, [
        el("span", { className: "server-glyph", attrs: { "aria-hidden": "true" } }),
        el("span", { className: "tile-title" }, [el("strong", { text: nodeLabel(node) }), ...(modelLine ? [modelLine] : []), el("small", { text: guestSummary(node) })]),
        statePill(node.state),
      ]),
      ...(online
        ? [el("div", { className: "tile-readings" }, [
            el("div", { className: "gauges" }, gauges),
            el("div", { className: "tile-details" }, [el("div", { className: "facts" }, [fact("CPU", formatCores(node.resources)), fact("RAM", memoryText)]), ...hardwareDetails]),
          ])]
        : [el("p", { className: "offline-note", text: "No live readings." }), ...hardwareDetails]),
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
  required("#guests-title").textContent = state.selectedNode === null ? "Guests" : `Guests on ${displayNodeName(state.selectedNode)}`;
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
    return el("li", { className: "guest", attrs: { style: colorStyle(colorOfNode(guest.node)) } }, [
      el("span", { className: "guest-mark", attrs: { "aria-hidden": "true" } }, [
        el("span", { className: `guest-icon guest-${guest.kind}`, text: kindLabel(guest.kind) }),
        el("span", { className: "guest-badge", text: initialOfNode(guest.node) }),
      ]),
      el("div", { className: "guest-body" }, [
        el("strong", { className: "guest-name", text: guestLabel(guest) }),
        el("div", { className: "guest-sub" }, [el("small", { text: `${displayNodeName(guest.node)} · ID ${guest.vmid}` }), statePill(guest.state)]),
        ...(metrics === null ? [] : [el("div", { className: "guest-metrics" }, [metricRow({ label: "CPU", metric: metrics.cpu, tone: "cpu" }), metricRow({ label: "RAM", metric: metrics.ram, tone: "memory" })])]),
      ]),
    ]);
  });
  const empty = nodes.length === 0 ? "No guests to show." : "No guests match this view.";
  required("#guest-list").replaceChildren(...(rows.length ? rows : [el("li", { className: "empty", text: empty })]));
}

function renderDevices() {
  const status = required("#devices-status");
  const error = devicesError ?? devicesSnapshot?.error;
  const stale = devicesSnapshot?.stale || error != null;
  status.classList.toggle("is-stale", Boolean(stale));
  status.textContent = error
    ? `${error}${devicesSnapshot?.fetched_at ? " Showing last-known leases." : ""}`
    : devicesSnapshot === null ? "Loading DHCP leases…" : `${devicesSnapshot.source} · ${devicesSnapshot.router}`;
  const leases = devicesSnapshot?.leases ?? [];
  const rows = leases.map((lease) => el("li", { className: "device" }, [
    el("strong", { text: lease.display_name, attrs: { title: lease.hostname ?? "Unnamed device" } }),
    el("span", { className: "device-address", text: lease.address }),
    el("small", { text: lease.mac.toUpperCase() }),
  ]));
  required("#device-list").replaceChildren(...(rows.length ? rows : [el("li", { className: "empty", text: error ? "Leases unavailable." : devicesSnapshot === null ? "" : "No unexpired DHCPv4 leases." })]));
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

function render() {
  const nodes = state.snapshot?.nodes ?? [];
  renderBanner();
  renderNodeList(nodes);
  renderOverview(nodes);
  renderTopology(nodes);
  renderGuests(nodes);
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

const refreshSeconds = REFRESH_INTERVAL_MS / 1000;
required("#refresh-note").textContent = `Read-only · checks for updates every ${refreshSeconds === 1 ? "second" : `${refreshSeconds} seconds`}`;
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
