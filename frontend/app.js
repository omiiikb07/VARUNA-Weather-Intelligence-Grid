const API = "http://127.0.0.1:8000";


// -------------------------
// MAP
// -------------------------

const map = L.map("map").setView([22.5, 79.0], 5);

L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        attribution: "&copy; OpenStreetMap contributors"
    }
).addTo(map);


let markers = [];


// -------------------------
// LOAD EVENTS
// -------------------------

async function loadEvents() {

    try {

        const response = await fetch(`${API}/events`);

        const data = await response.json();

        displayEvents(data.events);

        updateStats(data.events);

        updateSyncTime();

    } catch (error) {

        console.error("Could not connect to VARUNA:", error);

    }
}


// -------------------------
// DISPLAY EVENTS
// -------------------------

function displayEvents(events) {

    const list = document.getElementById("eventList");

    list.innerHTML = "";

    markers.forEach(marker => map.removeLayer(marker));

    markers = [];

    document.getElementById("eventCount").innerText =
        `${events.length} EVENTS`;


    if (events.length === 0) {

        list.innerHTML = `
            <div class="empty">
                No active weather events
            </div>
        `;

        return;
    }


    events.forEach(event => {

        const card = document.createElement("div");

        card.className = "event-card";

        card.innerHTML = `
            <div class="event-top">

                <div>

                    <div class="event-name">
                        ${event.city}
                    </div>

                    <div class="event-type">
                        ${event.event_type}
                    </div>

                </div>

                <div class="confidence">
                    ${event.confidence}%
                </div>

            </div>

            <div class="event-meta">

                <span>
                    ${event.report_count} REPORTS
                </span>

                <span>
                    ${event.status}
                </span>

            </div>
        `;


        card.onclick = () => {

            map.setView(
                [event.latitude, event.longitude],
                9
            );

        };


        list.appendChild(card);


        // MAP MARKER

        const marker = L.circleMarker(
            [event.latitude, event.longitude],
            {
                radius: 9,
                color: "#ff5d5d",
                fillColor: "#ff5d5d",
                fillOpacity: 0.8
            }
        ).addTo(map);


        marker.bindPopup(`
            <strong>${event.city}</strong><br>
            ${event.event_type}<br>
            Confidence: ${event.confidence}%<br>
            Reports: ${event.report_count}
        `);


        markers.push(marker);

    });
}


// -------------------------
// STATISTICS
// -------------------------

async function updateStats(events) {

    try {

        const response = await fetch(`${API}/reports`);

        const reports = await response.json();

        document.getElementById(
            "activeEvents"
        ).innerText = events.length;


        document.getElementById(
            "reportsAnalyzed"
        ).innerText = reports.length;


        if (reports.length > 0) {

            const average =
                reports.reduce(
                    (sum, report) =>
                        sum + report.trust_score,
                    0
                ) / reports.length;

            document.getElementById(
                "verifiedReports"
            ).innerText =
                `${Math.round(average)}%`;

        }


        document.getElementById(
            "highSeverity"
        ).innerText =
            events.filter(
                e => e.confidence >= 85
            ).length;

    } catch (error) {

        console.error(error);

    }
}


// -------------------------
// CLOCK
// -------------------------

function updateSyncTime() {

    const now = new Date();

    document.getElementById(
        "lastSync"
    ).innerText =
        now.toLocaleTimeString();

}


// -------------------------
// AUTO REFRESH
// -------------------------

loadEvents();

setInterval(
    loadEvents,
    10000
);