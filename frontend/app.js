const API = "http://127.0.0.1:8000";

const REFRESH_INTERVAL = 10000;

let reports = [];

let events = [];

let analyticsData = null;

let overviewMap = null;

let liveMap = null;

let overviewMarkers = null;

let liveMarkers = null;

let eventMarkerLookup = new Map();

let selectedEventMarkers = { overview: null, live: null };

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

    return date.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" });

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

        new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" });

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

    if (overviewMap) overviewMarkers = L.layerGroup().addTo(overviewMap);

    if (liveMap) liveMarkers = L.layerGroup().addTo(liveMap);

    addMapLegend("map");

    addMapLegend("liveMap");

    const overviewNote = document.querySelector("#overviewPage .map-note");

    const liveNote = document.querySelector("#livePage .map-note");

    if (overviewNote) {

        overviewNote.textContent = "Markers use report coordinates when available; otherwise, supported cities use approximate city-center locations. Severity is estimated from event type.";

    }

    if (liveNote) {

        liveNote.textContent = "Some markers use approximate city-center locations when GPS coordinates are unavailable. Severity is a prototype estimate based on event type.";

    }

}

function hasCoordinates(event) {

    if (event.latitude === null || event.latitude === undefined ||

        event.longitude === null || event.longitude === undefined ||

        String(event.latitude).trim() === "" ||

        String(event.longitude).trim() === "") {

        return false;

    }

    const latitude = Number(event.latitude);

    const longitude = Number(event.longitude);

    return Number.isFinite(latitude) && Number.isFinite(longitude) &&

        latitude >= -90 && latitude <= 90 &&

        longitude >= -180 && longitude <= 180;

}

// Approximate city-center coordinates are only a display fallback when GPS is absent.

// These are not report-specific or precise locations.

const APPROXIMATE_CITY_COORDINATES = {

    "ahmedabad": [23.0225, 72.5714],

    "bengaluru": [12.9716, 77.5946],

    "bangalore": [12.9716, 77.5946],

    "bhopal": [23.2599, 77.4126],

    "chandigarh": [30.7333, 76.7794],

    "chennai": [13.0827, 80.2707],

    "coimbatore": [11.0168, 76.9558],

    "delhi": [28.6139, 77.2090],

    "new delhi": [28.6139, 77.2090],

    "guwahati": [26.1445, 91.7362],

    "hubballi": [15.3647, 75.1240],

    "hyderabad": [17.3850, 78.4867],

    "indore": [22.7196, 75.8577],

    "jaipur": [26.9124, 75.7873],

    "kochi": [9.9312, 76.2673],

    "kolkata": [22.5726, 88.3639],

    "lucknow": [26.8467, 80.9462],

    "mumbai": [19.0760, 72.8777],

    "mysore": [12.2958, 76.6394],

    "mysuru": [12.2958, 76.6394],

    "mangaluru": [12.9141, 74.8560],

    "nagpur": [21.1458, 79.0882],

    "pune": [18.5204, 73.8567],

    "patna": [25.5941, 85.1376],

    "jodhpur": [26.2389, 73.0243],

    "vijayawada": [16.5062, 80.6480],

    "varanasi": [25.3176, 82.9739],

    "bhubaneswar": [20.2961, 85.8245],

    "srinagar": [34.0837, 74.7973],

    "thiruvananthapuram": [8.5241, 76.9366],

    "trivandrum": [8.5241, 76.9366],

    "visakhapatnam": [17.6868, 83.2185]

};

function getEventLocation(event) {

    if (hasCoordinates(event)) {

        return {

            coordinates: [Number(event.latitude), Number(event.longitude)],

            approximate: false

        };

    }

    const city = String(event.city || "").trim().toLowerCase().replace(/\s+/g, " ");

    const coordinates = APPROXIMATE_CITY_COORDINATES[city];

    return coordinates

        ? { coordinates, approximate: true }

        : null;

}

function getEstimatedSeverity(event) {

    const type = String(event.event_type || "").toLowerCase();

    if (/flood|cyclone|landslide|tsunami/.test(type)) return "Critical";

    if (/heat ?wave|extreme heat|thunderstorm|heavy rain|severe storm|hail/.test(type)) return "High";

    if (/rain|storm|strong wind|wind/.test(type)) return "Moderate";

    if (/clear|cloud|sunny|partly cloudy|mainly clear/.test(type)) return "Low";

    return "Unclassified";

}

function severityColor(severity) {

    const colors = {

        Critical: "#ff5d5d",

        High: "#f0ad4e",

        Moderate: "#f5cf62",

        Low: "#55d6b7",

        Unclassified: "#94a3b8"

    };

    return colors[severity] || colors.Unclassified;

}

function eventKey(event) {

    return [event.city, event.state, event.event_type]

        .map(value => String(value || "").trim().toLowerCase())

        .join("|");

}

function focusEventOnMap(map, event, mapName) {

    const location = getEventLocation(event);

    if (!map || !location) {

        showToast("No GPS or known city location is available for this event.", true);

        return;

    }

    // Animate the map toward the selected event for clearer navigation.
    map.flyTo(location.coordinates, 11, {

        animate: true,

        duration: 0.8

    });

    const markersForEvent = eventMarkerLookup.get(eventKey(event));

    const marker = markersForEvent && markersForEvent[mapName];

    if (marker) {

        const previousMarker = selectedEventMarkers[mapName];

        // Restore the previously selected marker to its normal appearance.
        if (previousMarker && previousMarker !== marker && previousMarker._varunaDefaultStyle) {

            previousMarker.setStyle(previousMarker._varunaDefaultStyle);

        }

        // Make the selected marker stand out without changing its severity color.
        marker.setStyle({ radius: 12, weight: 4, fillOpacity: 1 });

        selectedEventMarkers[mapName] = marker;

        marker.openPopup();

    }

}

function addEventMarkers(map, markerLayer, eventList, mapName) {

    if (!map || !markerLayer) return;

    markerLayer.clearLayers();

    eventList.forEach(event => {

        const location = getEventLocation(event);

        if (!location) return;

        const severity = getEstimatedSeverity(event);

        const color = severityColor(severity);

        const marker = L.circleMarker(location.coordinates, {

            radius: severity === "Critical" ? 10 : 8,

            color,

            fillColor: color,

            fillOpacity: 0.82,

            weight: 2

        });

        // Save the normal style so it can be restored after another event is selected.
        marker._varunaDefaultStyle = {

            radius: marker.options.radius,

            color: marker.options.color,

            fillColor: marker.options.fillColor,

            fillOpacity: marker.options.fillOpacity,

            weight: marker.options.weight

        };

        const locationLabel = location.approximate

            ? "Approximate city-center location"

            : "Report coordinates";

        const popup = `

            <strong>${escapeHTML(event.city || "Unknown location")}</strong><br>

            ${escapeHTML(event.state || "")}<br>

            Event: ${escapeHTML(event.event_type || "Unclassified")}<br>

            Estimated severity: ${escapeHTML(severity)}<br>

            Confidence: ${escapeHTML(event.confidence ?? "N/A")}%<br>

            Unique reports: ${escapeHTML(event.report_count ?? 0)}<br>

            Submitted reports: ${escapeHTML(event.submitted_report_count ?? event.report_count ?? 0)}<br>

            <small>${locationLabel}</small>

        `;

        marker.bindPopup(popup);

        marker.addTo(markerLayer);

        const key = eventKey(event);

        if (!eventMarkerLookup.has(key)) {

            eventMarkerLookup.set(key, {});

        }

        eventMarkerLookup.get(key)[mapName] = marker;

    });

}

function addMapLegend(elementId) {

    const mapElement = document.getElementById(elementId);

    if (!mapElement || mapElement.parentElement.querySelector(".map-severity-legend")) return;

    const legend = document.createElement("div");

    legend.className = "map-severity-legend";

    legend.setAttribute("aria-label", "Estimated event severity legend");

    legend.style.cssText = "display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;margin:9px 0 2px;font-size:11px;color:#9fb3c8;";

    [

        ["Critical", "#ff5d5d"],

        ["High", "#f0ad4e"],

        ["Moderate", "#f5cf62"],

        ["Low", "#55d6b7"],

        ["Unclassified", "#94a3b8"]

    ].forEach(([label, color]) => {

        const item = document.createElement("span");

        item.style.cssText = "display:inline-flex;align-items:center;gap:5px;";

        const dot = document.createElement("i");

        dot.style.cssText = `display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};`;

        item.append(dot, document.createTextNode(label));

        legend.appendChild(item);

    });

    mapElement.insertAdjacentElement("afterend", legend);

}

function refreshMaps() {

    eventMarkerLookup = new Map();

    selectedEventMarkers = { overview: null, live: null };

    addEventMarkers(overviewMap, overviewMarkers, events, "overview");

    addEventMarkers(liveMap, liveMarkers, events, "live");

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

        // Start at the identifying columns when opening the review table.
        const verificationTable = document.querySelector(".verification-table-wrap");
        if (verificationTable) verificationTable.scrollLeft = 0;

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

async function loadAnalytics() {

    const data = await fetchJSON(`${API}/analytics`);

    analyticsData = data && typeof data === "object" ? data : null;

    renderAnalytics();

}

async function loadAllData() {

    const results = await Promise.allSettled([

        loadEvents(),

        loadReports(),

        loadAnalytics()

    ]);

    const eventsLoaded = results[0].status === "fulfilled";

    const reportsLoaded = results[1].status === "fulfilled";

    const analyticsLoaded = results[2].status === "fulfilled";

    // Events and reports power the core dashboard; analytics is an additional endpoint.

    setConnection(eventsLoaded && reportsLoaded);

    if (eventsLoaded || reportsLoaded || analyticsLoaded) {

        updateSyncTime();

    }

    if (!eventsLoaded) {

        console.error("Could not load events:", results[0].reason);

    }

    if (!reportsLoaded) {

        console.error("Could not load reports:", results[1].reason);

    }

    if (!analyticsLoaded) {

        analyticsData = null;

        console.error("Could not load analytics:", results[2].reason);

        renderAnalytics();

    }

    if (!eventsLoaded && !reportsLoaded) {

        showToast("Could not connect to VARUNA backend.", true);

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

        const livePageActive = document.getElementById("livePage")

            ?.classList.contains("active");

        const targetMap = livePageActive ? liveMap : overviewMap;

        focusEventOnMap(targetMap, event, livePageActive ? "live" : "overview");

    });

    return card;

}

function fillEventList(elementId, eventList) {

    const list = document.getElementById(elementId);

    list.innerHTML = "";

    if (!eventList.length) {

        list.innerHTML = `<div class="empty">No weather events available</div>`;

        return;

    }

    eventList.forEach(event => {

        list.appendChild(createEventCard(event));

    });

}

function displayOverviewEvents() {

    document.getElementById("eventCount").textContent =

        `${events.length} EVENT GROUPS`;

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

function assessmentClass(value) {
    const status = String(value || "Uncertain").toLowerCase();
    if (status === "weather-supported") return "weather-supported";
    if (status === "source validated") return "source-validated";
    return "uncertain";
}

function renderVerification() {

    const body = document.getElementById("verificationTableBody");

    if (!body) return;

    const search = (

        document.getElementById("reportSearch")?.value || ""

    ).trim().toLowerCase();

    const selectedStatus =

        document.getElementById("statusFilter")?.value || "All";

    const selectedAssessment =

        document.getElementById("assessmentFilter")?.value || "All";

    const filteredReports = [...reports]

        .sort((a, b) => Number(b.id) - Number(a.id))

        .filter(report => {

            const status = canonicalStatus(report.verification_status);

            const matchesStatus =

                selectedStatus === "All" || status === selectedStatus;

            const assessment = report.assessment_status || "Uncertain";

            const matchesAssessment =

                selectedAssessment === "All" || assessment === selectedAssessment;

            const searchable = [

                report.id,

                report.text,

                report.city,

                report.state,

                report.event_type,

                report.source,

                status,

                assessment,

                report.assessment_reason

            ].join(" ").toLowerCase();

            return matchesStatus && matchesAssessment && searchable.includes(search);

        });

    if (!filteredReports.length) {

        body.innerHTML = `

            <tr>

                <td colspan="9" class="empty-cell">

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

                <td class="assessment-cell">
                    <span class="assessment-pill ${assessmentClass(report.assessment_status)}">
                        ${escapeHTML(report.assessment_status || "Uncertain")}
                    </span>
                    <div class="assessment-score">
                        Assessment score:
                        <strong>${report.assessment_score === null || report.assessment_score === undefined
                            ? "Not recorded" : `${escapeHTML(report.assessment_score)}/100`}</strong>
                    </div>
                    <div class="assessment-reason">
                        ${escapeHTML(report.assessment_reason || "No automated assessment reason available.")}
                    </div>
                    ${Array.isArray(report.assessment_evidence) && report.assessment_evidence.length
                        ? `<ul class="assessment-evidence">${report.assessment_evidence.map(item => `<li>${escapeHTML(item)}</li>`).join("")}</ul>`
                        : `<div class="assessment-evidence-empty">${report.assessment_score === null || report.assessment_score === undefined
                            ? "Evidence not recorded for this older report."
                            : "No additional evidence details returned."}</div>`}
                </td>

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

document.getElementById("assessmentFilter")

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

    // Use backend analytics when available; otherwise fall back to loaded reports.

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

        eventTypeCounts[eventType] = (eventTypeCounts[eventType] || 0) + 1;

        sourceCounts[source] = (sourceCounts[source] || 0) + 1;

        statusCounts[status] += 1;

    });

    const exactDuplicates = events.reduce(

        (sum, event) => sum + Number(event.duplicate_count || 0), 0

    );

    const nearDuplicates = events.reduce(

        (sum, event) => sum + Number(event.near_duplicate_count || 0), 0

    );

    const apiTypes = analyticsData?.reports_by_event_type;

    const apiStatuses = analyticsData?.reports_by_verification_status;

    const displayedEventTypes = Array.isArray(apiTypes)

        ? Object.fromEntries(apiTypes.map(item => [

            item.event_type || "Unknown", Number(item.count || 0)

        ]))

        : eventTypeCounts;

    const displayedStatuses = Array.isArray(apiStatuses)

        ? Object.fromEntries(apiStatuses.map(item => [

            canonicalStatus(item.status), Number(item.count || 0)

        ]))

        : statusCounts;

    const total = Number.isFinite(Number(analyticsData?.total_reports))

        ? Number(analyticsData.total_reports)

        : reports.length;

    const totalEvents = Number.isFinite(Number(analyticsData?.total_events))

        ? Number(analyticsData.total_events)

        : events.length;

    const verified = Number(displayedStatuses["Verified"] || 0);

    document.getElementById("analyticsTotal").textContent = total;

    document.getElementById("analyticsEvents").textContent = totalEvents;

    document.getElementById("analyticsVerified").textContent = verified;

    document.getElementById("analyticsDuplicates").textContent =

        exactDuplicates + nearDuplicates;

    renderBars("eventTypeAnalytics", displayedEventTypes);

    renderBars("sourceAnalytics", sourceCounts);

    renderBars("statusAnalytics", displayedStatuses);

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
