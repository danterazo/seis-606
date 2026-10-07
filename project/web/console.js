const $ = (selector) => document.querySelector(selector);

function percent(value) {
  return value == null ? null : `${value}%`;
}

function setUnknownAwareValue(selector, value, fallback = "Not supplied") {
  const element = $(selector);
  const known = value !== null && value !== undefined && value !== "";
  element.textContent = known ? String(value) : fallback;
  element.classList.toggle("unknown-value", !known);
  return known;
}

function displayReport(report) {
  const nodes = Array.isArray(report.nodes) ? report.nodes : [];
  const node = report.primary_node || nodes.find((item) => item.name?.toLowerCase() === "cerulean") || nodes[0];
  if (!node) throw new Error("The PVE source returned no node records.");

  const live = report.is_live === true;
  const reportedState = String(node.reported_state || "unknown").toLowerCase();
  const otherNodes = nodes.filter((item) => item.node_id !== node.node_id);
  const cpu = percent(node.cpu_percent);
  const memory = percent(node.memory_percent);
  const workloadCounts = node.workloads;
  const guestCountKnown = workloadCounts && typeof workloadCounts === "object";
  const vmCount = guestCountKnown ? Number(workloadCounts.VM || 0) : null;
  const lxcCount = guestCountKnown ? Number(workloadCounts.LXC || 0) : null;
  const resourceSummary = cpu || memory ? `CPU ${cpu || "—"} / MEM ${memory || "—"}` : null;
  const guestsSummary = guestCountKnown ? `${vmCount} VM / ${lxcCount} LXC` : null;
  const downCount = report.down_count;

  $("#source-label").textContent = report.source_label || "STATUS REPORT";
  $(".header-source").classList.toggle("is-live", live);
  $(".header-source").classList.toggle("is-manual", !live);
  $(".header-source").classList.remove("is-error");
  $("#host-name").textContent = node.name.toUpperCase();
  $("#host-address").textContent = node.address || report.address || "Not supplied";
  $("#known-up").textContent = String(report.known_up_count ?? (node.reported_state === "up" ? 1 : 0)).padStart(2, "0");
  $("#other-state").textContent = report.other_nodes_state || (downCount == null ? "UNKNOWN" : `${downCount} DOWN`);
  $("#other-detail").textContent = live
    ? `${otherNodes.length} other node${otherNodes.length === 1 ? "" : "s"} in cluster`
    : "Count and names not supplied";
  $("#host-state").textContent = reportedState.toUpperCase();
  $(".state-readout").classList.toggle("is-down", ["down", "offline", "stopped"].includes(reportedState));
  $(".state-readout").classList.toggle("is-unknown", !["up", "online", "running", "down", "offline", "stopped"].includes(reportedState));
  $("#record-name").textContent = node.name;
  $("#record-address").textContent = node.address || report.address || "Not supplied";
  $("#record-state").textContent = reportedState.replace(/^./, (character) => character.toUpperCase());
  $("#hero-state-note").textContent = live ? `PVE NODE / ${nodes.length} IN CLUSTER` : "OPERATOR-REPORTED STATE";
  $("#report-source-note").textContent = live ? "LIVE STATUS / READ ONLY" : "MANUAL STATUS / NOT POLLED";
  $("#last-updated").textContent = live && report.last_updated_at
    ? `LAST CHECK / ${new Date(report.last_updated_at).toLocaleTimeString()}`
    : "SOURCE / OPERATOR REPORT";
  $("#resource-summary").textContent = resourceSummary || "—";
  $("#resource-detail").textContent = resourceSummary ? "Live host utilization" : "Telemetry not supplied";
  $("#guest-summary").textContent = guestsSummary || "—";
  $("#guest-detail").textContent = guestCountKnown ? "PVE-reported guests" : "Inventory not supplied";

  setUnknownAwareValue("#record-architecture", node.architecture);
  setUnknownAwareValue("#record-resources", resourceSummary);
  setUnknownAwareValue("#record-guests", guestsSummary);

  if (live) {
    $("#report-lead").textContent = `${node.name} is ${reportedState}; ${report.known_up_count} of ${nodes.length} PVE node${nodes.length === 1 ? "" : "s"} online.`;
    $("#report-detail").textContent = downCount > 0
      ? `${downCount} other node${downCount === 1 ? " is" : "s are"} down. Values shown come from read-only PVE cluster resources.`
      : "Values shown come from read-only PVE cluster resources. No guest or host settings are changed.";
    $("#report-source-label").textContent = "LIVE PVE / SSH";
  } else {
    $("#report-lead").textContent = `${node.name} is the only PVE node currently reported up.`;
    $("#report-detail").textContent = "Other PVE nodes are reported down. Their names and total count were not provided, so this view does not invent an inventory.";
    $("#report-source-label").textContent = "MANUALLY SUPPLIED STATUS";
  }

  $(".host-hero").hidden = false;
  $(".telemetry-row").hidden = false;
  $(".readout-grid").hidden = false;
  $("#report-error").hidden = true;
}

function showError(error) {
  $("#source-label").textContent = "PVE STATUS UNAVAILABLE";
  $(".header-source").classList.remove("is-live", "is-manual");
  $(".header-source").classList.add("is-error");
  $(".host-hero").hidden = true;
  $(".telemetry-row").hidden = true;
  $(".readout-grid").hidden = true;
  $("#report-error-message").textContent = error.message;
  $("#report-error").hidden = false;
}

let toastTimer;
function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2200);
}

async function loadReport({ quiet = true } = {}) {
  const refreshButton = $("#refresh-status");
  refreshButton.disabled = true;
  refreshButton.classList.add("is-loading");
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const report = await response.json();
    if (!response.ok) throw new Error(report.error || "Status report unavailable.");
    displayReport(report);
    if (!quiet) showToast("PVE status refreshed");
  } catch (error) {
    showError(error);
  } finally {
    refreshButton.disabled = false;
    refreshButton.classList.remove("is-loading");
  }
}

$("#refresh-status").addEventListener("click", () => loadReport({ quiet: false }));
$("#copy-address").addEventListener("click", async () => {
  const address = $("#host-address").textContent;
  try {
    await navigator.clipboard.writeText(address);
    showToast(`Copied ${address}`);
  } catch {
    showToast("Clipboard access is unavailable in this browser");
  }
});

loadReport();
window.setInterval(() => loadReport(), 30000);
