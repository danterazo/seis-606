// @ts-check

/**
 * @typedef {{ cpu_ratio: number | null, cpu_cores: number | null, memory_used_bytes: number | null, memory_total_bytes: number | null }} Resources
 * @typedef {"running" | "stopped" | "paused" | "unknown"} GuestState
 * @typedef {{ vmid: number, name: string, node: string, kind: "vm" | "container", state: GuestState, resources: Resources }} Guest
 * @typedef {{ name: string, display_name: string, state: "online" | "offline" | "unknown", address: string | null, image: string | null, color: string, resources: Resources, guests: Guest[] }} PveNode
 * @typedef {{ source: string, fetched_at: string, nodes: PveNode[] }} Snapshot
 * @typedef {"all" | "running" | "vm" | "container"} GuestFilter
 * @typedef {{ snapshot: Snapshot | null, error: string | null, selectedNode: string | null, filter: GuestFilter, query: string }} ViewState
 * @typedef {{ className?: string, text?: string, attrs?: Readonly<Record<string, string>> }} ElementOptions
 */

const STATUS_URL = "/api/status";
const REFRESH_INTERVAL_MS = 30_000;
const MAX_TOPOLOGY_GUESTS = 12;
const TOPOLOGY_NAME_LIMIT = 22;
const BYTES_PER_MIB = 1024 ** 2;
const BYTES_PER_GIB = 1024 ** 3;
const SVG_NS = "http://www.w3.org/2000/svg";

/** @type {ViewState} */
const state = { snapshot: null, error: null, selectedNode: null, filter: "all", query: "" };

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

/** Memory under 1 GB reads better in MB; both halves of a pair share one unit. */
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
  let usedText = trimNumber(used / unit.size, unit.digits);
  // A small but real reading should not be shown as zero.
  if (usedText === "0" && used > 0) usedText = trimNumber(used / unit.size, 2);
  return `${usedText}/${trimNumber(total / unit.size, unit.digits)} ${unit.label}`;
}

/** @param {Resources} resources */
const formatCores = ({ cpu_cores: cores }) => (cores === null ? "cores unknown" : `${cores} ${cores === 1 ? "core" : "cores"}`);

/** Allotment, usage, then percentage: "3/8 GB (38%)". @param {Resources} resources */
function formatRam(resources) {
  const { memory_used_bytes: used, memory_total_bytes: total } = resources;
  if (total === null) return "unknown";
  if (used === null) return `${formatBytes(total)} total`;
  return `${formatMemoryPair({ used, total })} (${formatPercent(memoryPercent(resources))})`;
}

/** @param {Guest} guest @returns {[string, string]} */
function guestUsageLines(guest) {
  const { resources } = guest;
  if (guest.state !== "running") {
    const allotment = resources.memory_total_bytes === null ? "RAM allotment unknown" : `${formatBytes(resources.memory_total_bytes)} RAM allotted`;
    return [formatCores(resources), `Not running · ${allotment}`];
  }
  return [`${formatCores(resources)} · CPU ${formatPercent(cpuPercent(resources))}`, `RAM ${formatRam(resources)}`];
}

/** @param {Guest} guest */
function guestTooltip(guest) {
  const [compute, ram] = guestUsageLines(guest);
  return `${guest.name} (ID ${guest.vmid}) – ${guest.state}\n${compute}\n${ram}`;
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

/** @param {Guest["kind"]} kind */
const kindLabel = (kind) => (kind === "vm" ? "VM" : "LXC");

/** Capitalized name for display; the raw name stays the identifier. @param {PveNode} node */
const nodeLabel = (node) => node.display_name || node.name;

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

/** @param {{ label: string, value: number | null, tone: "cpu" | "memory" }} args */
function bar({ label, value, tone }) {
  const fill = el("span", { className: `bar-fill bar-${tone}` });
  fill.style.width = `${value ?? 0}%`;
  return el("div", { className: "bar-row" }, [
    el("span", { className: "bar-label", text: label }),
    el("span", { className: "bar-track" }, [fill]),
    el("span", { className: "bar-value", text: formatPercent(value) }),
  ]);
}

function renderBanner() {
  const banner = required("#banner");
  const { snapshot, error } = state;
  /** @type {{ tone: string, title: string, detail: string }} */
  let content;
  if (error !== null) {
    content = { tone: "alert", title: "Can't Reach Proxmox", detail: error };
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

/** @param {PveNode[]} nodes */
function renderOverview(nodes) {
  const tiles = nodes.map((node) =>
    el("button", { className: `tile tile-${node.state}`, attrs: { type: "button", style: colorStyle(node.color), "data-node": node.name, "aria-pressed": String(state.selectedNode === node.name) } }, [
      el("span", { className: "server-glyph large", attrs: { "aria-hidden": "true" } }),
      el("strong", { text: nodeLabel(node) }),
      statePill(node.state),
      el("small", { text: guestSummary(node) }),
      el("div", { className: "gauges" }, [gauge({ label: "CPU", value: cpuPercent(node.resources), tone: "cpu" }), gauge({ label: "RAM", value: memoryPercent(node.resources), tone: "memory" })]),
    ]),
  );
  required("#overview").replaceChildren(...(tiles.length ? tiles : [el("p", { className: "empty", text: "Nothing to show yet." })]));
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
          svgText({ x: gx + pill.badge + 8, y: gy + 19.5, text: truncate(guest.name, TOPOLOGY_NAME_LIMIT), className: "topo-guest-name", anchor: "start" }),
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

/** @param {PveNode[]} nodes */
function renderUsage(nodes) {
  const rows = nodes.map((node) =>
    el("div", { className: "usage-node" }, [
      el("strong", { text: nodeLabel(node) }),
      bar({ label: "CPU", value: cpuPercent(node.resources), tone: "cpu" }),
      bar({ label: "RAM", value: memoryPercent(node.resources), tone: "memory" }),
      el("small", { className: "usage-detail", text: `${formatCores(node.resources)} · RAM ${formatRam(node.resources)}` }),
    ]),
  );
  required("#usage").replaceChildren(...(rows.length ? rows : [el("p", { className: "empty", text: "No usage data." })]));
}

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
    .filter((guest) => query === "" || `${guest.name} ${guest.vmid} ${guest.node}`.toLowerCase().includes(query));
}

/** @param {PveNode[]} nodes */
function renderGuests(nodes) {
  required("#guests-title").textContent = state.selectedNode === null ? "Guests" : `Guests on ${displayNodeName(state.selectedNode)}`;
  required("#chips").replaceChildren(
    ...FILTERS.map(({ id, label }) => el("button", { className: "chip", text: label, attrs: { type: "button", "data-filter": id, "aria-pressed": String(state.filter === id) } })),
  );

  const guests = visibleGuests(nodes);
  const rows = guests.map((guest) => {
    const [compute, ram] = guestUsageLines(guest);
    return el("li", { className: "guest", attrs: { style: colorStyle(colorOfNode(guest.node)) } }, [
      el("span", { className: `guest-icon guest-${guest.kind}`, text: kindLabel(guest.kind), attrs: { "aria-hidden": "true" } }),
      el("span", { className: "guest-meta" }, [
        el("strong", { text: guest.name }),
        el("small", { text: `${displayNodeName(guest.node)} · ID ${guest.vmid}` }),
        el("small", { text: compute }),
        el("small", { text: ram }),
      ]),
      statePill(guest.state),
    ]);
  });
  const empty = nodes.length === 0 ? "No guests to show." : "No guests match this view.";
  required("#guest-list").replaceChildren(...(rows.length ? rows : [el("li", { className: "empty", text: empty })]));
}

function render() {
  const nodes = state.snapshot?.nodes ?? [];
  renderBanner();
  renderNodeList(nodes);
  renderOverview(nodes);
  renderTopology(nodes);
  renderUsage(nodes);
  renderGuests(nodes);
  required("#source-label").textContent = state.snapshot?.source ?? "No data source connected";
  required("#updated").textContent = state.snapshot ? `Updated ${new Date(state.snapshot.fetched_at).toLocaleTimeString()}` : state.error ? "Update failed" : "Connecting…";
}

/** @param {unknown} payload */
function errorMessage(payload) {
  return typeof payload === "object" && payload !== null && "error" in payload && typeof payload.error === "string" ? payload.error : "Status is unavailable.";
}

async function refresh() {
  const button = required("#refresh-button");
  button.setAttribute("disabled", "");
  button.classList.add("is-loading");
  try {
    const response = await fetch(STATUS_URL, { cache: "no-store" });
    /** @type {unknown} */
    const payload = await response.json();
    if (!response.ok) throw new Error(errorMessage(payload));
    const snapshot = /** @type {Snapshot} */ (payload);
    state.snapshot = snapshot;
    state.error = null;
    if (state.selectedNode !== null && !snapshot.nodes.some((node) => node.name === state.selectedNode)) state.selectedNode = null;
  } catch (error) {
    state.snapshot = null;
    state.error = error instanceof Error ? error.message : "Status is unavailable.";
  } finally {
    button.removeAttribute("disabled");
    button.classList.remove("is-loading");
    render();
  }
}

/** @param {string} name */
function toggleNode(name) {
  state.selectedNode = state.selectedNode === name ? null : name;
  render();
}

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
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
required("#refresh-button").addEventListener("click", () => void refresh());

render();
void refresh();
window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
