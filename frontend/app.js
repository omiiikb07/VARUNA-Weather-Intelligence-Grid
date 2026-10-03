
const API = "http://127.0.0.1:8000";

const REFRESH_INTERVAL = 10000;

let reports = [];
let events = [];
let overviewMap = null;
let liveMap = null;
let overviewMarkers = null;
let liveMarkers = null;
let toastTimer = null;

const pageInfo = {
    overview: {
        title: "India Situation Room",
        subtitle: "Weather intelligence and event monitoring"
    },
    live: {
        title: "Live Weather Events",
        subtitle: "Geospatial monitoring of aggregated reports"
    },
    verification: {
        title: "Report Verification",
        subtitle: "Review and update incoming weather reports"
    },
    analytics: {
        title: "Weather Analytics",
        subtitle: "Insights from reports currently in the database"
    }
};


// -------------------------
// HELPERS
// -------------------------

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

function canonicalStatus(status) {
    const value = String(status || "Pending").trim().toLowerCase();

    if (value === "verified") return "Verified";
    if (value === "rejected") return "Rejected";
    if (value === "under review") return "Under Review";

    return "Pending";
}

function statusClass(status) {
    return canonicalStatus(status)
        .toLowerCase()
        .replace(/\s+/g, "-");
}

function formatDate(value) {
    if (!value) return "Time unavailable";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Time unavailable";
    }

    return date.toLocaleString();
}

function showToast(message, isError = false) {
    const toast = document.getElementById("toast");

    toast.textContent = message;
    toast.style.borderColor = isError ? "#a94747" : "#236c60";
    toast.style.background = isError ? "#3c2023" : "#12352f";
    toast.style.color = isError ? "#ff8580" : "#69dfc1";
    toast.classList.add("show");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

function setConnection(connected) {
    const dot = document.getElementById("connectionDot");
    const status = document.getElementById("connectionStatus");

    dot.classList.toggle("online", connected);
    status.textContent = connected ? "Connected" : "Offline";
}

function updateSyncTime() {
    document.getElementById("lastSync").textContent =
        new Date().toLocaleTimeString();
}

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        cache: "no-store",
        ...options,
        headers: {
            ...(options.headers || {})
        }
    });

    if (!response.ok) {
        let message = `Request failed (${response.status})`;

        try {
            const body = await response.json();
            message = body.detail || message;
        } catch (_) {
            // Keep the default message if response is not JSON.
        }

        throw new Error(message);
    }

    return response.json();
}


// -------------------------
// MAPS
// -------------------------

function createMap(elementId) {
    const element = document.getElementById(elementId);

    if (!element || typeof L === "undefined") {
        return null;
    }

    const map = L.map(elementId).setView([22.5, 79.0], 5);

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution: "&copy; OpenStreetMap contributors",
            maxZoom: 18
        }
    ).addTo(map);

    return map;
}

function initializeMaps() {
    overviewMap = createMap("map");
    liveMap = createMap("liveMap");

    if (overviewMap) {
        overviewMarkers = L.layerGroup().addTo(overviewMap);
    }

    if (liveMap) {
        liveMarkers = L.layerGroup().addTo(liveMap);
    }
}

function hasCoordinates(event) {
    return (
        Number.isFinite(Number(event.latitude)) &&
        Number.isFinite(Number(event.longitude)) &&
        event.latitude !== null &&
        event.longitude !== null
    );
}

function eventColor(event) {
    const type = String(event.event_type || "").toLowerCase();

    if (type.includes("flood")) return "#ff5d5d";
    if (type.includes("heat")) return "#f0ad4e";
    if (type.includes("storm")) return "#a88bff";
    if (type.includes("rain")) return "#55a9e8";

    return "#55d6b7";
}

function focusEventOnMap(map, event) {
    if (!map || !hasCoordinates(event)) {
        showToast("No GPS coordinates are available for this event.", true);
        return;
    }

    map.setView(
        [Number(event.latitude), Number(event.longitude)],
        10
    );
}

function addEventMarkers(map, markerLayer, eventList) {
    if (!map || !markerLayer) return;

    markerLayer.clearLayers();

    eventList.forEach(event => {
        if (!hasCoordinates(event)) return;

        const color = eventColor(event);

        const marker = L.circleMarker(
            [Number(event.latitude), Number(event.longitude)],
            {
                radius: 8,
                color,
                fillColor: color,
                fillOpacity: 0.8,
                weight: 2
            }
        );

        const popup = `
            <strong>${escapeHTML(event.city)}</strong><br>
            ${escapeHTML(event.event_type)}<br>
            Confidence: ${escapeHTML(event.confidence)}%<br>
            Unique reports: ${escapeHTML(event.report_count)}<br>
            Submitted reports: ${escapeHTML(event.submitted_report_count)}
        `;

        marker.bindPopup(popup);
        marker.addTo(markerLayer);
    });
}

function refreshMaps() {
    addEventMarkers(overviewMap, overviewMarkers, events);
    addEventMarkers(liveMap, liveMarkers, events);
}

function resizeVisibleMap() {
    if (overviewMap &&
        document.getElementById("overviewPage").classList.contains("active")) {
        overviewMap.invalidateSize();
    }

    if (liveMap &&
        document.getElementById("livePage").classList.contains("active")) {
        liveMap.invalidateSize();
    }
}


// -------------------------
// NAVIGATION
// -------------------------

function switchView(viewName) {
    const validViews = ["overview", "live", "verification", "analytics"];

    if (!validViews.includes(viewName)) return;

    document.querySelectorAll(".page").forEach(page => {
        page.classList.remove("active");
    });

    document.querySelectorAll(".nav-item").forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.view === viewName
        );
    });

    const page = document.getElementById(`${viewName}Page`);

    if (page) page.classList.add("active");

    document.getElementById("pageTitle").textContent =
        pageInfo[viewName].title;

    document.getElementById("pageSubtitle").textContent =
        pageInfo[viewName].subtitle;

    resizeVisibleMap();

    if (viewName === "verification") {
        renderVerification();
    }

    if (viewName === "analytics") {
        renderAnalytics();
    }
}

document.querySelectorAll(".nav-item").forEach(button => {
    button.addEventListener("click", () => {
        switchView(button.dataset.view);
    });
});

document.getElementById("adminButton").addEventListener("click", () => {
    switchView("verification");
});


// -------------------------
// LOAD BACKEND DATA
// -------------------------

async function loadEvents() {
    const data = await fetchJSON(`${API}/events`);
    events = Array.isArray(data.events) ? data.events : [];

    displayOverviewEvents();
    displayLiveEvents();
    updateEventStats();
    refreshMaps();
}

async function loadReports() {
    const data = await fetchJSON(`${API}/reports`);
    reports = Array.isArray(data) ? data : [];

    updateReportStats();
    renderVerification();
    renderAnalytics();
    renderActivity();
}

async function loadAllData() {
    try {
        const results = await Promise.allSettled([
            loadEvents(),
            loadReports()
        ]);

        const eventsLoaded = results[0].status === "fulfilled";
        const reportsLoaded = results[1].status === "fulfilled";

        setConnection(eventsLoaded && reportsLoaded);

        if (eventsLoaded || reportsLoaded) {
            updateSyncTime();
        }

        if (!eventsLoaded) {
            console.error("Could not load events:", results[0].reason);
        }

        if (!reportsLoaded) {
            console.error("Could not load reports:", results[1].reason);
        }

        if (!eventsLoaded && !reportsLoaded) {
            showToast("Could not connect to VARUNA backend.", true);
        }
    } catch (error) {
        console.error("Backend error:", error);
        setConnection(false);
    }
}


// -------------------------
// EVENT CARDS
// -------------------------

function createEventCard(event) {
    const card = document.createElement("div");
    card.className = "event-card";

    const verifiedCount = Number(event.verified_report_count || 0);
    const uniqueCount = Number(event.report_count || 0);

    card.innerHTML = `
        <div class="event-top">
            <div>
                <div class="event-name">${escapeHTML(event.city)}</div>
                <div class="event-type">${escapeHTML(event.event_type)}</div>
            </div>
            <div class="confidence">${escapeHTML(event.confidence)}%</div>
        </div>

        <div class="event-meta">
            <span>${escapeHTML(uniqueCount)} UNIQUE REPORTS</span>
            <span>${escapeHTML(event.status || "ACTIVE")}</span>
        </div>

        <div class="event-meta">
            <span>${escapeHTML(event.submitted_report_count ?? uniqueCount)} SUBMITTED</span>
            <span class="event-tag ${verifiedCount > 0 ? "verified" : ""}">
                ${verifiedCount} VERIFIED
            </span>
        </div>
    `;

    card.addEventListener("click", () => {
        focusEventOnMap(overviewMap, event);

        if (!overviewMap || !hasCoordinates(event)) {
            focusEventOnMap(liveMap, event);
        }
    });

    return card;
}

function fillEventList(elementId, eventList) {
    const list = document.getElementById(elementId);
    list.innerHTML = "";

    if (!eventList.length) {
        list.innerHTML = `<div class="empty">No active weather events</div>`;
        return;
    }

    eventList.forEach(event => {
        list.appendChild(createEventCard(event));
    });
}

function displayOverviewEvents() {
    document.getElementById("eventCount").textContent =
        `${events.length} EVENTS`;

    fillEventList("eventList", events);
}

function displayLiveEvents() {
    document.getElementById("liveEventCount").textContent =
        `${events.length} events`;

    fillEventList("liveEventList", events);
}


// -------------------------
// OVERVIEW STATISTICS
// -------------------------

function updateEventStats() {
    document.getElementById("activeEvents").textContent = events.length;

    const highConfidenceCount = events.filter(
        event => Number(event.confidence) >= 85
    ).length;

    document.getElementById("highSeverity").textContent =
        highConfidenceCount;
}

function updateReportStats() {
    const total = reports.length;

    const verified = reports.filter(
        report => canonicalStatus(report.verification_status) === "Verified"
    ).length;

    const percentage = total
        ? Math.round((verified / total) * 100)
        : 0;

    document.getElementById("reportsAnalyzed").textContent = total;
    document.getElementById("verifiedReports").textContent = `${percentage}%`;
    document.getElementById("verifiedSubtext").textContent =
        `${verified} of ${total} reports verified`;

    document.getElementById("totalReportCount").textContent = total;
    document.getElementById("pendingReportCount").textContent =
        reports.filter(r => canonicalStatus(r.verification_status) === "Pending").length;
    document.getElementById("verifiedReportCount").textContent = verified;
    document.getElementById("rejectedReportCount").textContent =
        reports.filter(r => canonicalStatus(r.verification_status) === "Rejected").length;
}


// -------------------------
// ACTIVITY
// -------------------------

function renderActivity() {
    const container = document.getElementById("activityList");

    const latestReports = [...reports]
        .sort((a, b) => {
            return new Date(b.timestamp || 0) - new Date(a.timestamp || 0);
        })
        .slice(0, 5);

    if (!latestReports.length) {
        container.innerHTML = `
            <div class="empty">No reports received yet</div>
        `;
        return;
    }

    container.innerHTML = latestReports.map(report => `
        <div class="activity">
            <span class="activity-dot"></span>
            <div>
                <strong>
                    ${escapeHTML(report.event_type || "Weather report")}
                    — ${escapeHTML(report.city || "Unknown")}
                </strong>
                <small>
                    ${escapeHTML(canonicalStatus(report.verification_status))}
                    · ${escapeHTML(formatDate(report.timestamp))}
                </small>
            </div>
        </div>
    `).join("");
}


// -------------------------
// VERIFICATION TABLE
// -------------------------

function renderVerification() {
    const body = document.getElementById("verificationTableBody");

    if (!body) return;

    const search = (
        document.getElementById("reportSearch")?.value || ""
    ).trim().toLowerCase();

    const selectedStatus =
        document.getElementById("statusFilter")?.value || "All";

    const filteredReports = [...reports]
        .sort((a, b) => Number(b.id) - Number(a.id))
        .filter(report => {
            const status = canonicalStatus(report.verification_status);

            const matchesStatus =
                selectedStatus === "All" || status === selectedStatus;

            const searchable = [
                report.id,
                report.text,
                report.city,
                report.state,
                report.event_type,
                report.source,
                status
            ].join(" ").toLowerCase();

            return matchesStatus && searchable.includes(search);
        });

    if (!filteredReports.length) {
        body.innerHTML = `
            <tr>
                <td colspan="8" class="empty-cell">
                    No matching reports found.
                </td>
            </tr>
        `;
        return;
    }

    body.innerHTML = filteredReports.map(report => {
        const status = canonicalStatus(report.verification_status);

        return `
            <tr data-report-row="${Number(report.id)}">
                <td>${escapeHTML(report.id)}</td>
                <td class="report-text">
                    ${escapeHTML(report.text)}
                    <div class="muted">${escapeHTML(formatDate(report.timestamp))}</div>
                </td>
                <td>
                    ${escapeHTML(report.city)}, ${escapeHTML(report.state)}
                </td>
                <td>${escapeHTML(report.event_type || "Unknown")}</td>
                <td>${escapeHTML(report.source || "Unknown")}</td>
                <td>${escapeHTML(report.trust_score ?? 0)}%</td>
                <td>
                    <span class="status-pill ${statusClass(status)}">
                        ${escapeHTML(status)}
                    </span>
                </td>
                <td>
                    <div class="status-action">
                        <select class="status-select"
                                aria-label="New status for report ${Number(report.id)}"
                                data-status-id="${Number(report.id)}">
                            ${["Pending", "Verified", "Under Review", "Rejected"]
                                .map(option => `
                                    <option value="${option}"
                                        ${status === option ? "selected" : ""}>
                                        ${option}
                                    </option>
                                `).join("")}
                        </select>
                        <button class="save-btn"
                                data-save-id="${Number(report.id)}">
                            Save
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function showVerificationNotice(message, type = "success") {
    const notice = document.getElementById("verificationNotice");
    notice.textContent = message;
    notice.className = `verification-notice ${type}`;
}

async function saveVerification(reportId) {
    const select = document.querySelector(
        `[data-status-id="${reportId}"]`
    );

    const button = document.querySelector(
        `[data-save-id="${reportId}"]`
    );

    if (!select || !button) return;

    const status = select.value;
    button.disabled = true;
    button.textContent = "Saving...";

    try {
        const result = await fetchJSON(
            `${API}/reports/${reportId}/verification`,
            {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ status })
            }
        );

        const report = reports.find(
            item => Number(item.id) === Number(reportId)
        );

        if (report) {
            report.verification_status = result.verification_status || status;
        }

        updateReportStats();
        renderVerification();
        renderAnalytics();
        renderActivity();

        showVerificationNotice(
            `Report #${reportId} updated to ${status}.`
        );
        showToast(`Report #${reportId} updated.`);
    } catch (error) {
        console.error("Verification update failed:", error);
        showVerificationNotice(
            `Could not update report #${reportId}: ${error.message}`,
            "error"
        );
        showToast("Could not save verification status.", true);
        button.disabled = false;
        button.textContent = "Save";
    }
}

document.getElementById("verificationTableBody")
    .addEventListener("click", event => {
        const button = event.target.closest("[data-save-id]");

        if (!button) return;

        saveVerification(Number(button.dataset.saveId));
    });

document.getElementById("reportSearch")
    .addEventListener("input", renderVerification);

document.getElementById("statusFilter")
    .addEventListener("change", renderVerification);


// -------------------------
// ANALYTICS
// -------------------------

function renderBars(elementId, data) {
    const container = document.getElementById(elementId);
    const entries = Object.entries(data)
        .sort((a, b) => b[1] - a[1]);

    if (!entries.length) {
        container.innerHTML = `<div class="empty">No data available</div>`;
        return;
    }

    const maxValue = Math.max(...entries.map(([, count]) => count), 1);

    container.innerHTML = entries.map(([label, count]) => {
        const width = Math.max(0, (count / maxValue) * 100);

        return `
            <div class="bar-item">
                <div class="bar-label-row">
                    <span>${escapeHTML(label)}</span>
                    <strong>${count}</strong>
                </div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:${width}%"></div>
                </div>
            </div>
        `;
    }).join("");
}

function renderAnalytics() {
    const total = reports.length;
    const verified = reports.filter(
        report => canonicalStatus(report.verification_status) === "Verified"
    ).length;

    const eventTypeCounts = {};
    const sourceCounts = {};
    const statusCounts = {
        "Verified": 0,
        "Pending": 0,
        "Under Review": 0,
        "Rejected": 0
    };

    reports.forEach(report => {
        const eventType = report.event_type || "Unknown";
        const source = report.source || "Unknown";
        const status = canonicalStatus(report.verification_status);

        eventTypeCounts[eventType] =
            (eventTypeCounts[eventType] || 0) + 1;

        sourceCounts[source] =
            (sourceCounts[source] || 0) + 1;

        statusCounts[status] += 1;
    });

    const exactDuplicates = events.reduce(
        (sum, event) => sum + Number(event.duplicate_count || 0),
        0
    );

    const nearDuplicates = events.reduce(
        (sum, event) => sum + Number(event.near_duplicate_count || 0),
        0
    );

    document.getElementById("analyticsTotal").textContent = total;
    document.getElementById("analyticsEvents").textContent = events.length;
    document.getElementById("analyticsVerified").textContent = verified;
    document.getElementById("analyticsDuplicates").textContent =
        exactDuplicates + nearDuplicates;

    renderBars("eventTypeAnalytics", eventTypeCounts);
    renderBars("sourceAnalytics", sourceCounts);
    renderBars("statusAnalytics", statusCounts);
}


// -------------------------
// MANUAL REFRESH BUTTONS
// -------------------------

document.getElementById("refreshEventsButton")
    .addEventListener("click", async () => {
        try {
            await loadEvents();
            showToast("Events refreshed.");
        } catch (error) {
            console.error(error);
            showToast("Could not refresh events.", true);
        }
    });

document.getElementById("refreshReportsButton")
    .addEventListener("click", async () => {
        try {
            await loadReports();
            showToast("Reports refreshed.");
        } catch (error) {
            console.error(error);
            showToast("Could not refresh reports.", true);
        }
    });

document.getElementById("refreshAnalyticsButton")
    .addEventListener("click", loadAllData);


// -------------------------
// INITIALIZE
// -------------------------

initializeMaps();
loadAllData();

setInterval(loadAllData, REFRESH_INTERVAL);

window.addEventListener("resize", resizeVisibleMap);
