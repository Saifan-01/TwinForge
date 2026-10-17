/**
 * Plant Alpha console: polling, plant map, device management, query views, fault lab.
 */

let devicesCache = [];
let telemetryCache = [];
let simRunning = false;
let autoPollTimer = null;
let editingDeviceId = null;

const PAGE_TITLES = {
    "tab-twin-map": "Plant floor",
    "tab-devices": "Devices",
    "tab-query-unusual": "Unusual today",
    "tab-query-failure": "Failure risk",
    "tab-telemetry": "Live readings",
    "tab-benchmark": "Index performance",
    "tab-fault-lab": "Fault lab",
};

const ZONE_BOXES = {
    "ZONE-MACHINING-B": { xMin: 6, xMax: 45, yMin: 20, yMax: 44 },
    "ZONE-ASSEMBLY-A": { xMin: 56, xMax: 95, yMin: 20, yMax: 44 },
    "ZONE-LOGISTICS-C": { xMin: 6, xMax: 30, yMin: 66, yMax: 91 },
    "ZONE-ENERGY-D": { xMin: 39, xMax: 61, yMin: 66, yMax: 91 },
    "ZONE-CLEANROOM-E": { xMin: 71, xMax: 94, yMin: 66, yMax: 91 },
};

document.addEventListener("DOMContentLoaded", initDashboard);
document.addEventListener("keydown", e => {
    if (e.key === "Escape") document.querySelectorAll(".modal.open").forEach(m => m.classList.remove("open"));
});

/* ---------- Helpers ---------- */

function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function toast(message, kind = "") {
    const box = document.getElementById("toasts");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

/** fetch wrapper: adds the CSRF header, sends the user to /login when the session ends. */
async function api(url, options = {}) {
    const opts = { credentials: "same-origin", ...options };
    opts.headers = { "X-Requested-With": "dashboard", ...(options.headers || {}) };
    if (opts.body && typeof opts.body !== "string") {
        opts.body = JSON.stringify(opts.body);
        opts.headers["Content-Type"] = "application/json";
    }
    const res = await fetch(url, opts);
    if (res.status === 401) {
        window.location.href = "/login";
        throw new Error("Session expired");
    }
    let data = {};
    try { data = await res.json(); } catch (_) { /* empty body */ }
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
}

function formatTime(value) {
    return value ? new Date(value).toLocaleTimeString() : "";
}

function statusBadge(status) {
    const cls = status === "CRITICAL" ? "badge-danger" : (status === "WARNING" ? "badge-warning" : (status === "ONLINE" || status === "OK" ? "badge-success" : ""));
    return `<span class="badge ${cls}">${escapeHtml(status)}</span>`;
}

function prettyType(type) {
    return String(type || "").toLowerCase().replace(/_/g, " ");
}

/* ---------- Startup, polling, tabs ---------- */

async function initDashboard() {
    await Promise.allSettled([
        updateOverview(), fetchDevicesAndRenderMap(), fetchAlerts(), fetchUnusualEvents(),
        fetchFailurePrediction(), fetchTelemetryCards(), checkSimulatorStatus(), fetchBenchmarkReport(),
    ]);
    if (autoPollTimer) clearInterval(autoPollTimer);
    autoPollTimer = setInterval(pollRealtimeData, 3500);
}

async function pollRealtimeData() {
    await updateOverview();
    await fetchAlerts();
    await checkSimulatorStatus();
    if (document.getElementById("tab-telemetry").classList.contains("active")) await fetchTelemetryCards();
}

function switchTab(tabId) {
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    const pane = document.getElementById(tabId);
    if (pane) pane.classList.add("active");
    const btn = Array.from(document.querySelectorAll(".tab-btn")).find(b => b.getAttribute("onclick").includes(`'${tabId}'`));
    if (btn) btn.classList.add("active");
    document.getElementById("pageTitle").textContent = PAGE_TITLES[tabId] || "";

    if (tabId === "tab-query-unusual") fetchUnusualEvents();
    if (tabId === "tab-query-failure") fetchFailurePrediction();
    if (tabId === "tab-telemetry") fetchTelemetryCards();
    if (tabId === "tab-benchmark") fetchBenchmarkReport();
    if (tabId === "tab-devices") fetchDevicesAndRenderMap();
}

/* ---------- Overview strip ---------- */

async function updateOverview() {
    try {
        const data = await api("/api/analytics/overview");
        document.getElementById("valTotalDevices").textContent = data.totalDevices || 0;
        document.getElementById("valTotalEvents").textContent = (data.totalEvents || 0).toLocaleString();
        document.getElementById("valActiveAlerts").textContent = data.activeAlerts || 0;
        document.getElementById("subDeviceStatus").innerHTML =
            `${data.onlineDevices} online, <span class="text-warning">${data.warningDevices} warning</span>, <span class="text-danger">${data.criticalDevices} critical</span>`;
        const navCount = document.getElementById("navAlertCount");
        navCount.textContent = data.activeAlerts || "";
        navCount.classList.toggle("show", (data.activeAlerts || 0) > 0);
    } catch (e) {
        console.error("Overview failed:", e);
    }
}

/* ---------- Plant floor map + devices table ---------- */

async function fetchDevicesAndRenderMap() {
    try {
        const json = await api("/api/devices");
        devicesCache = json.devices || [];
        renderMap();
        renderDevicesTable();
    } catch (e) {
        console.error("Device load failed:", e);
    }
}

function renderMap() {
    const layer = document.getElementById("mapDeviceLayer");
    layer.innerHTML = "";
    devicesCache.forEach((dev, idx) => {
        const box = ZONE_BOXES[dev.zoneId] || { xMin: 10, xMax: 90, yMin: 10, yMax: 90 };
        const fx = ((idx * 37) % 100) / 100;
        const fy = ((idx * 73) % 100) / 100;
        const dot = document.createElement("button");
        dot.className = `device-dot ${dev.status}`;
        dot.style.left = `${box.xMin + fx * (box.xMax - box.xMin)}%`;
        dot.style.top = `${box.yMin + fy * (box.yMax - box.yMin)}%`;
        dot.title = `${dev.deviceId}: ${dev.name} (${dev.status})`;
        dot.setAttribute("aria-label", `${dev.deviceId}, ${dev.status}`);
        dot.onclick = () => openDeviceModal(dev.deviceId);
        layer.appendChild(dot);
    });
}

function renderDevicesTable() {
    const tbody = document.getElementById("tbodyDevices");
    if (!tbody) return;
    const q = document.getElementById("deviceSearch").value.trim().toLowerCase();
    const type = document.getElementById("deviceTypeFilter").value;
    const status = document.getElementById("deviceStatusFilter").value;
    const list = devicesCache.filter(d =>
        (!q || d.deviceId.toLowerCase().includes(q) || (d.name || "").toLowerCase().includes(q)) &&
        (!type || d.type === type) && (!status || d.status === status));
    document.getElementById("deviceCount").textContent = `${list.length} of ${devicesCache.length}`;

    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No devices match these filters.</td></tr>';
        return;
    }
    tbody.innerHTML = list.map(d => `
        <tr class="${d.status === "CRITICAL" ? "row-critical" : (d.status === "WARNING" ? "row-warning" : "")}">
            <td><a href="#" onclick="openDeviceModal('${escapeHtml(d.deviceId)}'); return false;"><strong>${escapeHtml(d.deviceId)}</strong></a><br><small class="text-muted">${escapeHtml(d.name)}</small></td>
            <td>${escapeHtml(prettyType(d.type))}</td>
            <td class="zone-cell"><small>${escapeHtml(d.zoneId)}</small></td>
            <td>${statusBadge(d.status)}</td>
            <td>${(d.capabilities || []).map(c => `<span class="chip">${escapeHtml(c)}</span>`).join("")}</td>
            <td class="row-actions">
                <button class="btn btn-outline btn-sm admin-only" onclick="openDeviceForm('${escapeHtml(d.deviceId)}')">Edit</button>
                ${d.status !== "DECOMMISSIONED" ? `<button class="btn btn-outline btn-sm admin-only" onclick="decommissionDevice('${escapeHtml(d.deviceId)}')">Decommission</button>` : ""}
                <button class="btn btn-danger btn-sm admin-only" onclick="deleteDevice('${escapeHtml(d.deviceId)}')">Delete</button>
            </td>
        </tr>`).join("");
}

function openDeviceModal(deviceId) {
    const dev = devicesCache.find(d => d.deviceId === deviceId);
    if (!dev) return;
    document.getElementById("modalDeviceTitle").textContent = `${dev.deviceId}: ${dev.name}`;
    const coords = dev.location && dev.location.coordinates ? dev.location.coordinates.join(", ") : "none";
    document.getElementById("modalDeviceBody").innerHTML = `
        <dl class="kv">
            <dt>Type</dt><dd>${escapeHtml(prettyType(dev.type))}</dd>
            <dt>Zone</dt><dd>${escapeHtml(dev.zoneId)}</dd>
            <dt>Status</dt><dd>${statusBadge(dev.status)}</dd>
            <dt>Sensors</dt><dd>${(dev.capabilities || []).map(c => `<span class="chip">${escapeHtml(c)}</span>`).join("")}</dd>
            <dt>Position</dt><dd>${escapeHtml(coords)} (longitude, latitude)</dd>
            <dt>Firmware</dt><dd>${escapeHtml(dev.firmwareVersion || "unknown")}</dd>
            <dt>Last seen</dt><dd>${dev.lastSeen ? new Date(dev.lastSeen).toLocaleString() : "never"}</dd>
        </dl>
        <h4 style="margin-top:1rem">Hardware specs (stored as-is in the document)</h4>
        <pre class="json">${escapeHtml(JSON.stringify(dev.specs || {}, null, 2))}</pre>`;
    document.getElementById("deviceModal").classList.add("open");
}

function closeModal(id) {
    document.getElementById(id).classList.remove("open");
}

/* ---------- Device create / update / delete ---------- */

function openDeviceForm(deviceId = null) {
    editingDeviceId = deviceId;
    const dev = deviceId ? devicesCache.find(d => d.deviceId === deviceId) : null;
    document.getElementById("deviceFormTitle").textContent = dev ? `Edit ${dev.deviceId}` : "Add device";
    document.getElementById("deviceFormError").classList.add("hidden");
    const idField = document.getElementById("fDeviceId");
    idField.value = dev ? dev.deviceId : "";
    idField.disabled = !!dev;
    document.getElementById("fName").value = dev ? dev.name : "";
    document.getElementById("fType").value = dev ? dev.type : "CNC_MILL";
    document.getElementById("fType").disabled = !!dev;
    document.getElementById("fZone").value = dev ? dev.zoneId : document.getElementById("fZone").options[0]?.value;
    document.getElementById("fStatus").value = dev ? dev.status : "ONLINE";
    document.getElementById("fFirmware").value = dev ? (dev.firmwareVersion || "") : "v1.0.0";
    document.getElementById("fCaps").value = dev ? (dev.capabilities || []).join(", ") : "";
    const coords = dev && dev.location ? dev.location.coordinates : [-84.388, 33.749];
    document.getElementById("fLng").value = coords[0];
    document.getElementById("fLat").value = coords[1];
    document.getElementById("fSpecs").value = dev && dev.specs && Object.keys(dev.specs).length ? JSON.stringify(dev.specs, null, 2) : "";
    document.getElementById("deviceFormModal").classList.add("open");
    (dev ? document.getElementById("fName") : idField).focus();
}

async function saveDevice() {
    const errBox = document.getElementById("deviceFormError");
    errBox.classList.add("hidden");

    let specs = {};
    const specText = document.getElementById("fSpecs").value.trim();
    if (specText) {
        try { specs = JSON.parse(specText); }
        catch (_) { return showFormError("Hardware specs must be valid JSON, for example {\"spindleMaxRpm\": 12000}."); }
        if (typeof specs !== "object" || Array.isArray(specs)) return showFormError("Hardware specs must be a JSON object.");
    }
    const lng = parseFloat(document.getElementById("fLng").value);
    const lat = parseFloat(document.getElementById("fLat").value);
    if (Number.isNaN(lng) || Number.isNaN(lat)) return showFormError("Longitude and latitude must be numbers.");

    const body = {
        name: document.getElementById("fName").value.trim(),
        zoneId: document.getElementById("fZone").value,
        status: document.getElementById("fStatus").value,
        firmwareVersion: document.getElementById("fFirmware").value.trim() || "v1.0.0",
        capabilities: document.getElementById("fCaps").value.split(",").map(s => s.trim()).filter(Boolean),
        specs,
        location: { type: "Point", coordinates: [lng, lat] },
    };
    const btn = document.getElementById("btnSaveDevice");
    btn.disabled = true;
    try {
        if (editingDeviceId) {
            await api(`/api/devices/${encodeURIComponent(editingDeviceId)}`, { method: "PUT", body });
            toast(`Saved changes to ${editingDeviceId}.`, "success");
        } else {
            body.deviceId = document.getElementById("fDeviceId").value.trim();
            body.type = document.getElementById("fType").value;
            await api("/api/devices", { method: "POST", body });
            toast(`Added ${body.deviceId}.`, "success");
        }
        closeModal("deviceFormModal");
        await fetchDevicesAndRenderMap();
        await updateOverview();
    } catch (e) {
        showFormError(e.message);
    } finally {
        btn.disabled = false;
    }
}

function showFormError(message) {
    const box = document.getElementById("deviceFormError");
    box.textContent = message;
    box.classList.remove("hidden");
}

async function decommissionDevice(deviceId) {
    if (!confirm(`Decommission ${deviceId}? It stays in the database with status DECOMMISSIONED.`)) return;
    try {
        await api(`/api/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE" });
        toast(`${deviceId} decommissioned.`, "success");
        await fetchDevicesAndRenderMap();
        await updateOverview();
    } catch (e) { toast(e.message, "error"); }
}

async function deleteDevice(deviceId) {
    if (!confirm(`Permanently delete ${deviceId}? This cannot be undone.`)) return;
    try {
        await api(`/api/devices/${encodeURIComponent(deviceId)}?hard=true`, { method: "DELETE" });
        toast(`${deviceId} deleted.`, "success");
        await fetchDevicesAndRenderMap();
        await updateOverview();
    } catch (e) { toast(e.message, "error"); }
}

/* ---------- Alerts ---------- */

async function fetchAlerts() {
    try {
        const data = await api("/api/alerts");
        const container = document.getElementById("alertsListContainer");
        const alerts = data.alerts || [];
        const open = alerts.filter(a => !a.acknowledged);
        document.getElementById("badgeAlertsCount").textContent = `${open.length} open`;

        if (alerts.length === 0) {
            container.innerHTML = '<div class="empty-state">No alerts. The plant is running normally.</div>';
            return;
        }
        container.innerHTML = alerts.map(a => `
            <div class="alert-item ${escapeHtml(a.severity)} ${a.acknowledged ? "acked" : ""}">
                <div class="alert-item-header">
                    <span>${escapeHtml(a.deviceId)}</span>
                    <span class="badge ${a.severity === "CRITICAL" ? "badge-danger" : "badge-warning"}">${escapeHtml(a.severity)}</span>
                </div>
                <div class="alert-msg">${escapeHtml(a.message)}</div>
                <div class="alert-meta">
                    <span>${formatTime(a.ts)}</span>
                    ${a.acknowledged ? "<span>Acknowledged</span>"
                        : `<button class="btn btn-outline btn-sm admin-only" onclick="acknowledgeAlert('${escapeHtml(a.alertId)}')">Acknowledge</button>`}
                </div>
            </div>`).join("");
    } catch (e) {
        console.error("Alerts failed:", e);
    }
}

async function acknowledgeAlert(alertId) {
    try {
        await api(`/api/alerts/${encodeURIComponent(alertId)}/ack`, { method: "POST" });
        toast("Alert acknowledged.", "success");
        await fetchAlerts();
        await updateOverview();
    } catch (e) { toast(e.message, "error"); }
}

/* ---------- Query 1: unusual events ---------- */

async function fetchUnusualEvents() {
    const hours = document.getElementById("unusualTimeWindow").value;
    const tbody = document.getElementById("tbodyUnusual");
    try {
        const data = await api(`/api/analytics/unusual-today?hours=${hours}&z_threshold=2.5`);
        const list = data.unusualEvents || [];
        document.getElementById("valUnusualCount").textContent = list.length;
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Nothing unusual in this window.</td></tr>';
            return;
        }
        tbody.innerHTML = list.map(item => {
            const reasons = (item.anomalyType || []).map(r => `<span class="tag-reason">${escapeHtml(r)}</span>`).join("");
            const errors = (item.errors && item.errors.length)
                ? item.errors.map(err => `<span class="badge badge-danger">${escapeHtml(err)}</span>`).join(" ")
                : '<span class="text-muted">None</span>';
            const readings = Object.entries(item.readings || {}).map(([k, v]) => `${escapeHtml(k)} <strong>${escapeHtml(v)}</strong>`).join("<br>");
            return `<tr>
                <td class="num">${formatTime(item.ts)}</td>
                <td><strong>${escapeHtml(item.deviceId)}</strong><br><small class="text-muted">${escapeHtml(item.deviceName || "")}</small></td>
                <td><small>${escapeHtml(item.zoneId || "n/a")}</small></td>
                <td>${reasons}</td>
                <td class="num"><small>${readings}</small></td>
                <td>${errors}</td>
            </tr>`;
        }).join("");
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state text-danger">Query failed: ${escapeHtml(e.message)}</td></tr>`;
    }
}

/* ---------- Query 2: failure prediction ---------- */

async function fetchFailurePrediction() {
    const tbody = document.getElementById("tbodyFailure");
    try {
        const data = await api("/api/analytics/failure-risk?hours=12");
        const list = data.machines || [];
        document.getElementById("valHighRiskCount").textContent = list.filter(m => m.failureRiskScore >= 50).length;
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No machines evaluated yet. Seed data or start the simulator.</td></tr>';
            return;
        }
        const signed = n => (n > 0 ? `+${n}` : `${n}`);
        tbody.innerHTML = list.slice(0, 20).map((m, idx) => {
            const level = m.failureRiskScore >= 75 ? "crit" : (m.failureRiskScore >= 45 ? "warn" : "");
            const badge = m.riskCategory === "CRITICAL_FAILURE_IMMINENT" ? "badge-danger" : (m.riskCategory === "HIGH_MAINTENANCE_REQUIRED" ? "badge-warning" : "badge-success");
            return `<tr class="${level === "crit" ? "row-critical" : (level === "warn" ? "row-warning" : "")}">
                <td><strong class="num">#${idx + 1}</strong><br><span class="badge ${badge}">${escapeHtml(String(m.riskCategory).replace(/_/g, " ").toLowerCase())}</span></td>
                <td><strong>${escapeHtml(m.deviceId)}</strong><br><small class="text-muted">${escapeHtml(m.deviceName || "")}</small></td>
                <td><small>${escapeHtml(m.zoneId || "n/a")}</small><br><small class="text-muted">${escapeHtml(prettyType(m.deviceType))}</small></td>
                <td><div class="risk-cell"><strong>${escapeHtml(m.failureRiskScore)}</strong>
                    <div class="risk-bar"><span class="${level}" style="width:${Math.min(100, Math.max(0, Number(m.failureRiskScore) || 0))}%"></span></div></div></td>
                <td class="num">${escapeHtml(m.maxVibe)} <small class="text-muted">(${escapeHtml(signed(m.vibeDelta))})</small></td>
                <td class="num">${escapeHtml(m.maxTemp)} <small class="text-muted">(${escapeHtml(signed(m.tempDelta))})</small></td>
                <td>${m.errorCount > 0 ? `<span class="badge badge-danger">${escapeHtml(m.errorCount)}</span>` : '<span class="text-muted">0</span>'}</td>
            </tr>`;
        }).join("");
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state text-danger">Query failed: ${escapeHtml(e.message)}</td></tr>`;
    }
}

/* ---------- Live readings ---------- */

async function fetchTelemetryCards() {
    try {
        const data = await api("/api/events/latest?limit=60");
        telemetryCache = data.events || [];
        filterTelemetryCards();
    } catch (e) {
        document.getElementById("telemetryCardsGrid").innerHTML = `<div class="empty-state text-danger">Could not load readings: ${escapeHtml(e.message)}</div>`;
    }
}

function filterTelemetryCards() {
    const filter = document.getElementById("telemetryTypeFilter").value;
    const container = document.getElementById("telemetryCardsGrid");
    const list = filter === "ALL" ? telemetryCache : telemetryCache.filter(e => e.type === filter);
    if (list.length === 0) {
        container.innerHTML = '<div class="empty-state" style="grid-column:1/-1">No readings for this device type yet.</div>';
        return;
    }
    container.innerHTML = list.map(item => `
        <div class="telemetry-card ${escapeHtml(item.status)}">
            <div class="card-top">
                <div><div class="card-dev-id">${escapeHtml(item.deviceId)}</div><small class="text-muted">${escapeHtml(prettyType(item.type))}</small></div>
                ${statusBadge(item.status)}
            </div>
            ${Object.entries(item.readings || {}).map(([k, v]) =>
                `<div class="reading-row"><span class="text-muted">${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join("")}
            <div class="card-stamp">${formatTime(item.latestTs)}</div>
        </div>`).join("");
}

/* ---------- Simulator and fault lab ---------- */

async function checkSimulatorStatus() {
    try {
        const data = await api("/api/simulator/status");
        simRunning = data.isRunning;
        document.getElementById("simIndicator").className = simRunning ? "indicator running" : "indicator";
        document.getElementById("simStatusText").textContent = simRunning ? `Simulator running (${data.totalTicks} ticks)` : "Simulator stopped";
        document.getElementById("btnSimText").textContent = simRunning ? "Pause live readings" : "Start live readings";

        const box = document.getElementById("activeFaultsContainer");
        const faults = Object.entries(data.activeFaults || {});
        box.innerHTML = faults.length === 0
            ? '<span class="text-muted">No faults active. All machines are running at baseline.</span>'
            : faults.map(([devId, info]) => `
                <div class="fault-row">
                    <div><strong>${escapeHtml(devId)}</strong> <span class="badge badge-danger">${escapeHtml(String(info.type).replace(/_/g, " "))}</span>
                    <small class="text-muted">step ${escapeHtml(info.step)}</small></div>
                    <button class="btn btn-outline btn-sm admin-only" onclick="clearSingleFault('${escapeHtml(devId)}')">Clear</button>
                </div>`).join("");
    } catch (e) {
        console.error("Simulator status failed:", e);
    }
}

async function toggleSimulator() {
    try {
        await api(simRunning ? "/api/simulator/stop" : "/api/simulator/start", { method: "POST" });
        toast(simRunning ? "Simulator paused." : "Simulator started.", "success");
        await checkSimulatorStatus();
    } catch (e) { toast(e.message, "error"); }
}

async function injectSpecificFault(selectId, faultType) {
    const devId = document.getElementById(selectId).value;
    try {
        await api("/api/simulator/inject", { method: "POST", body: { deviceId: devId, faultType } });
        toast(`${faultType.replace(/_/g, " ")} started on ${devId}.${simRunning ? "" : " Start the simulator to see its effect."}`, "success");
        await Promise.all([checkSimulatorStatus(), fetchAlerts(), fetchUnusualEvents(), fetchFailurePrediction()]);
    } catch (e) { toast(e.message, "error"); }
}

async function clearSingleFault(devId) {
    try {
        await api("/api/simulator/clear", { method: "POST", body: { deviceId: devId } });
        toast(`Cleared fault on ${devId}.`, "success");
        await checkSimulatorStatus();
    } catch (e) { toast(e.message, "error"); }
}

async function clearAllFaults() {
    try {
        await api("/api/simulator/clear", { method: "POST", body: {} });
        toast("All faults cleared.", "success");
        await checkSimulatorStatus();
    } catch (e) { toast(e.message, "error"); }
}

/* ---------- Benchmark report (small markdown renderer) ---------- */

function renderMarkdown(md) {
    const inline = s => escapeHtml(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    const lines = md.split(/\r?\n/);
    let html = "", i = 0;
    while (i < lines.length) {
        const line = lines[i];
        if (/^```/.test(line)) {
            const code = [];
            i++;
            while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
            i++;
            html += `<pre>${escapeHtml(code.join("\n"))}</pre>`;
        } else if (/^\s*\|/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
            const cells = l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => inline(c.trim()));
            html += `<table><thead><tr>${cells(line).map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>`;
            i += 2;
            while (i < lines.length && /^\s*\|/.test(lines[i])) {
                html += `<tr>${cells(lines[i]).map(c => `<td>${c}</td>`).join("")}</tr>`;
                i++;
            }
            html += "</tbody></table>";
        } else if (/^#{1,4}\s/.test(line)) {
            const level = line.match(/^#+/)[0].length;
            html += `<h${level}>${inline(line.replace(/^#+\s*/, ""))}</h${level}>`;
            i++;
        } else if (line.trim()) {
            html += `<p>${inline(line)}</p>`;
            i++;
        } else {
            i++;
        }
    }
    return html;
}

async function fetchBenchmarkReport() {
    const container = document.getElementById("benchmarkReportContainer");
    try {
        const data = await api("/api/analytics/benchmark");
        container.innerHTML = data.reportMarkdown
            ? renderMarkdown(data.reportMarkdown)
            : '<div class="empty-state">No results yet. Run <code>python scripts/benchmark_indexes.py</code> to generate them.</div>';
    } catch (e) {
        container.innerHTML = `<div class="empty-state text-danger">Could not load results: ${escapeHtml(e.message)}</div>`;
    }
}
