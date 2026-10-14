
"use strict";

// ======================================================
// FLOODRA - DISASTER INTELLIGENCE DASHBOARD
// ======================================================

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
}

function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function fetchJSON(url) {
    const response = await fetch(url, { cache: "no-store" });

    if (!response.ok) {
        throw new Error(`${url} returned HTTP ${response.status}`);
    }

    return response.json();
}

function featuresOf(data) {
    return Array.isArray(data?.features) ? data.features : [];
}

function propertiesOf(feature) {
    return feature?.properties || {};
}

function formatNumber(value, digits = 0) {
    const number = Number(value);
    return Number.isFinite(number)
        ? number.toLocaleString(undefined, {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits
        })
        : "N/A";
}

// ======================================================
// MAP INITIALIZATION
// ======================================================

const map = L.map("map").setView([38.1058, -0.7589], 13);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

const floodLayer = L.layerGroup().addTo(map);
const roadLayer = L.layerGroup().addTo(map);
const isolationLayer = L.layerGroup().addTo(map);
const priorityLayer = L.layerGroup().addTo(map);
const connectivityLayer = L.layerGroup().addTo(map);

let layerControlCreated = false;

// ======================================================
// COLORS
// ======================================================

function roadColor(risk) {
    switch (String(risk || "").toUpperCase()) {
        case "HIGH RISK": return "#ff1744";
        case "MODERATE RISK": return "#ff9800";
        case "LOW RISK": return "#ffd600";
        default: return "#00e676";
    }
}

function priorityColor(level) {
    switch (String(level || "").toUpperCase()) {
        case "CRITICAL": return "#ff1744";
        case "HIGH": return "#ff6d00";
        case "MEDIUM": return "#ffd600";
        default: return "#00e676";
    }
}

function connectivityColor(status) {
    switch (String(status || "").toUpperCase()) {
        case "CONNECTED": return "#00e676";
        case "POTENTIALLY DISCONNECTED": return "#ff1744";
        default: return "#eab308";
    }
}

// ======================================================
// FLOOD OVERLAY
// ======================================================

async function loadFloodOverlay() {
    try {
        const bounds = await fetchJSON("/static/flood_overlay_bounds.json");

        const south = Number(bounds.south);
        const west = Number(bounds.west);
        const north = Number(bounds.north);
        const east = Number(bounds.east);

        if (![south, west, north, east].every(Number.isFinite)) {
            throw new Error("Invalid flood overlay bounds.");
        }

        const leafletBounds = [[south, west], [north, east]];

        const overlay = L.imageOverlay(
            "/static/flood_overlay.png",
            leafletBounds,
            { opacity: 0.6, interactive: false }
        );

        floodLayer.clearLayers();
        floodLayer.addLayer(overlay);

        map.fitBounds(leafletBounds, {
            padding: [30, 30],
            maxZoom: 14
        });

        console.log("Flood overlay loaded.");
    } catch (error) {
        console.error("Flood overlay error:", error);
    }
}

// ======================================================
// ROAD RISK LAYER
// ======================================================

async function loadRoads() {
    try {
        const data = await fetchJSON("/api/roads");
        const features = featuresOf(data);

        roadLayer.clearLayers();

        const layer = L.geoJSON(data, {
            style(feature) {
                const risk = String(
                    propertiesOf(feature).risk_level || "CLEAR"
                ).toUpperCase();

                return {
                    color: roadColor(risk),
                    weight: risk === "HIGH RISK" ? 6 : 4,
                    opacity: 0.9
                };
            },

            onEachFeature(feature, layer) {
                const p = propertiesOf(feature);
                const exposure = Number(p.flood_pct);

                layer.bindPopup(`
                    <div style="min-width:190px;font-family:Arial,sans-serif">
                        <h3>🚧 Road Analysis</h3>
                        <b>Road:</b> ${escapeHTML(p.name || "Unnamed road")}<br><br>
                        <b>Flood exposure:</b>
                        ${Number.isFinite(exposure) ? exposure.toFixed(2) + "%" : "N/A"}<br><br>
                        <b>Risk:</b> ${escapeHTML(p.risk_level || "UNKNOWN")}
                    </div>
                `);
            }
        });

        roadLayer.addLayer(layer);

        const highRisk = features.filter(feature =>
            String(propertiesOf(feature).risk_level || "").toUpperCase()
                === "HIGH RISK"
        ).length;

        setText("highRiskRoads", highRisk);

        console.log("Road features:", features.length);
        console.log("High-risk roads:", highRisk);
    } catch (error) {
        console.error("Road loading error:", error);
        setText("highRiskRoads", "N/A");
    }
}

// ======================================================
// ISOLATION LAYER
// ======================================================

async function loadIsolation() {
    try {
        const data = await fetchJSON("/api/isolation");
        const features = featuresOf(data);

        isolationLayer.clearLayers();

        const layer = L.geoJSON(data, {
            pointToLayer(feature, latlng) {
                const p = propertiesOf(feature);
                const level = String(p.isolation_level || "LOW").toUpperCase();

                return L.circleMarker(latlng, {
                    radius: level === "CRITICAL" ? 10 : 8,
                    fillColor: priorityColor(level),
                    color: "#ffffff",
                    weight: 1,
                    fillOpacity: 0.85
                });
            },

            onEachFeature(feature, layer) {
                const p = propertiesOf(feature);

                layer.bindPopup(`
                    <div style="min-width:190px;font-family:Arial,sans-serif">
                        <h3>⚠ Isolation Risk</h3>
                        <b>Settlement:</b> ${escapeHTML(p.name || "Unnamed settlement")}<br><br>
                        <b>Isolation level:</b> ${escapeHTML(p.isolation_level || "N/A")}<br>
                        <b>Isolation score:</b> ${formatNumber(p.isolation_score, 1)}<br>
                        <b>Nearest risky road:</b> ${formatNumber(p.nearest_risky_road_m)} m
                        <br><br><small>Heuristic estimate requiring verification.</small>
                    </div>
                `);
            }
        });

        isolationLayer.addLayer(layer);
        setText("isolationCount", features.length);

        console.log("Isolation locations:", features.length);
    } catch (error) {
        console.error("Isolation loading error:", error);
        setText("isolationCount", "N/A");
    }
}

// ======================================================
// RESCUE PRIORITY MAP LAYER
// ======================================================

async function loadPriority() {
    try {
        const data = await fetchJSON("/api/priority");
        const features = featuresOf(data);

        priorityLayer.clearLayers();

        const layer = L.geoJSON(data, {
            pointToLayer(feature, latlng) {
                const p = propertiesOf(feature);
                const level = String(p.priority_level || "LOW").toUpperCase();

                return L.circleMarker(latlng, {
                    radius: level === "CRITICAL" ? 12 : 9,
                    fillColor: priorityColor(level),
                    color: "#ffffff",
                    weight: 2,
                    fillOpacity: 0.9
                });
            },

            onEachFeature(feature, layer) {
                const p = propertiesOf(feature);

                layer.bindPopup(`
                    <div style="min-width:200px;font-family:Arial,sans-serif">
                        <h3>🚨 Rescue Priority</h3>
                        <b>Settlement:</b> ${escapeHTML(p.name || "Unnamed settlement")}<br><br>
                        <b>Priority:</b> ${escapeHTML(p.priority_level || "N/A")}<br>
                        <b>Rescue score:</b> ${formatNumber(p.rescue_score, 1)}/100<br>
                        <b>Isolation:</b> ${escapeHTML(p.isolation_level || "N/A")}<br>
                        <b>Nearest risky road:</b> ${escapeHTML(p.nearest_risky_road_level || "N/A")}<br><br>
                        <small>Score is a heuristic ranking, not a probability.</small>
                    </div>
                `);
            }
        });

        priorityLayer.addLayer(layer);

        const critical = features.filter(feature =>
            String(propertiesOf(feature).priority_level || "").toUpperCase()
                === "CRITICAL"
        ).length;

        setText("criticalCount", critical);

        console.log("Rescue-priority locations:", features.length);
    } catch (error) {
        console.error("Priority loading error:", error);
        setText("criticalCount", "N/A");
    }
}

// ======================================================
// CONNECTIVITY MAP LAYER
// ======================================================

async function loadConnectivity() {
    try {
        const data = await fetchJSON("/api/connectivity");
        const features = featuresOf(data);

        connectivityLayer.clearLayers();

        const layer = L.geoJSON(data, {
            pointToLayer(feature, latlng) {
                const p = propertiesOf(feature);
                const status = p.connectivity_status ||
                    (p.scenario_connected_to_largest_component === true
                        ? "CONNECTED"
                        : p.scenario_connected_to_largest_component === false
                            ? "POTENTIALLY DISCONNECTED"
                            : "UNKNOWN");

                return L.circleMarker(latlng, {
                    radius: 8,
                    color: "#ffffff",
                    weight: 2,
                    fillColor: connectivityColor(status),
                    fillOpacity: 0.9
                });
            },

            onEachFeature(feature, layer) {
                const p = propertiesOf(feature);

                const status = p.connectivity_status ||
                    (p.scenario_connected_to_largest_component === true
                        ? "CONNECTED"
                        : p.scenario_connected_to_largest_component === false
                            ? "POTENTIALLY DISCONNECTED"
                            : "UNKNOWN");

                layer.bindPopup(`
                    <div style="font-family:Arial,sans-serif">
                        <h3>🔗 Connectivity Scenario</h3>
                        <b>Settlement:</b> ${escapeHTML(p.name || "Unnamed settlement")}<br>
                        <b>Status:</b> ${escapeHTML(status)}<br>
                        <b>Nearest network node:</b> ${formatNumber(p.snap_distance_m)} m<br>
                        <b>Component size:</b> ${formatNumber(p.scenario_component_size)} nodes<br><br>
                        <small>Scenario estimate only; not verified road accessibility.</small>
                    </div>
                `);
            }
        });

        connectivityLayer.addLayer(layer);
        console.log("Connectivity locations:", features.length);
    } catch (error) {
        console.error("Connectivity layer error:", error);
    }
}

// ======================================================
// FLOOD AREA STATISTICS
// ======================================================

async function calculateFloodExtent() {
    try {
        const data = await fetchJSON("/api/flood-stats");

        if (data.status !== "OK") {
            throw new Error(data.message || "Flood statistics unavailable");
        }

        const area = Number(data.flood_area_km2);
        setText(
            "floodExtent",
            Number.isFinite(area) ? `${area.toFixed(3)} km²` : "N/A"
        );

        console.log("Flood area:", data.flood_area_km2);
    } catch (error) {
        console.error("Flood extent error:", error);
        setText("floodExtent", "N/A");
    }
}

// ======================================================
// DASHBOARD SUMMARY
// ======================================================

async function loadSummary() {
    try {
        const data = await fetchJSON("/api/summary");

        if (data.status !== "OK") {
            throw new Error("Dashboard summary unavailable");
        }

        setText("highRiskRoads", data.high_risk_roads);
        setText("isolationCount", data.isolation_risks);
        setText("criticalCount", data.critical_zones);

        console.log("Dashboard summary:", data);
    } catch (error) {
        console.warn("Summary API unavailable; using layer counts.", error);
    }
}

// ======================================================
// ANALYSIS REPORT
// ======================================================

async function loadAnalysisReport() {
    try {
        const data = await fetchJSON("/api/analysis-report");

        if (data.status !== "OK" || !data.report) {
            throw new Error(data.message || "Analysis report unavailable");
        }

        const report = data.report;
        const flood = report.flood_detection || {};
        const outputs = report.other_outputs || {};

        setText("reportStatus", "Analysis report loaded successfully.");
        setText("reportFloodPixels", formatNumber(flood.flooded_pixels));
        setText(
            "reportFloodPercentage",
            `${formatNumber(flood.flooded_pixel_percentage, 2)}%`
        );
        setText("reportRoadFeatures", formatNumber(outputs.road_features));
        setText(
            "reportIsolationLocations",
            formatNumber(outputs.isolation_locations)
        );
        setText(
            "reportPriorityLocations",
            formatNumber(outputs.rescue_priority_locations)
        );

        setText(
            "reportValidation",
            `Validation: ${report.validation_status || "UNKNOWN"}. Flood and rescue classifications are estimates, not verified emergency instructions.`
        );
    } catch (error) {
        console.error("Analysis report error:", error);
        setText("reportStatus", "Report unavailable. Check the analysis report API.");
        setText("reportValidation", "Validation status unavailable.");
    }
}

// ======================================================
// ROAD RISK DISTRIBUTION CHART
// ======================================================

async function loadRoadRiskChart() {
    const chart = document.getElementById("roadRiskChart");
    if (!chart) return;

    try {
        const data = await fetchJSON("/api/road-risk-summary");

        if (data.status !== "OK") {
            throw new Error("Road risk summary unavailable");
        }

        const distribution = data.risk_distribution || {};
        const total = Number(data.total_segments || 0);

        setText("roadRiskTotal", `${total.toLocaleString()} road segments analyzed`);
        chart.replaceChildren();

        const categories = [
            { label: "High Risk", key: "HIGH RISK", color: "#ff1744" },
            { label: "Moderate", key: "MODERATE RISK", color: "#ff9800" },
            { label: "Low Risk", key: "LOW RISK", color: "#ffd600" },
            { label: "Clear", key: "CLEAR", color: "#00e676" }
        ];

        categories.forEach(category => {
            const count = Number(distribution[category.key] || 0);
            const percentage = total > 0 ? count / total * 100 : 0;

            const row = document.createElement("div");
            row.className = "risk-row";

            const label = document.createElement("span");
            label.textContent = category.label;

            const track = document.createElement("div");
            track.className = "risk-track";

            const fill = document.createElement("div");
            fill.className = "risk-fill";
            fill.style.width = `${percentage}%`;
            fill.style.backgroundColor = category.color;
            track.appendChild(fill);

            const value = document.createElement("span");
            value.className = "risk-count";
            value.textContent =
                `${count.toLocaleString()} (${percentage.toFixed(1)}%)`;

            row.append(label, track, value);
            chart.appendChild(row);
        });
    } catch (error) {
        console.error("Road risk chart error:", error);
        chart.textContent = "Road risk distribution is unavailable.";
        setText("roadRiskTotal", "Unable to load road data.");
    }
}

// ======================================================
// RESCUE PRIORITY TABLE
// ======================================================

async function loadRescueTable() {
    const tbody = document.getElementById("rescueTableBody");
    if (!tbody) return;

    try {
        const data = await fetchJSON("/api/priority");
        const features = featuresOf(data);

        tbody.replaceChildren();

        if (!features.length) {
            const row = tbody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 4;
            cell.textContent = "No rescue-priority locations available.";
            return;
        }

        const rank = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

        features.sort((a, b) => {
            const pa = propertiesOf(a);
            const pb = propertiesOf(b);
            const levelA = String(pa.priority_level || "LOW").toUpperCase();
            const levelB = String(pb.priority_level || "LOW").toUpperCase();

            const difference = (rank[levelA] ?? 4) - (rank[levelB] ?? 4);
            return difference || Number(pb.rescue_score || 0) -
                Number(pa.rescue_score || 0);
        });

        for (const feature of features) {
            const p = propertiesOf(feature);
            const level = String(p.priority_level || "LOW").toUpperCase();
            const row = tbody.insertRow();

            row.insertCell().textContent = p.name || "Unnamed settlement";
            row.insertCell().textContent = p.isolation_level || "N/A";

            const score = Number(p.rescue_score);
            row.insertCell().textContent =
                Number.isFinite(score) ? `${score.toFixed(1)}/100` : "N/A";

            const priorityCell = row.insertCell();
            const badge = document.createElement("span");
            badge.className = `priority-badge priority-${level.toLowerCase()}`;
            badge.textContent = level;
            priorityCell.appendChild(badge);
        }
    } catch (error) {
        console.error("Rescue table error:", error);
        tbody.replaceChildren();
        const row = tbody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 4;
        cell.textContent = "Could not load rescue-priority data.";
    }
}

// ======================================================
// CONNECTIVITY SUMMARY
// ======================================================

async function loadConnectivitySummary() {
    try {
        const data = await fetchJSON("/api/connectivity-summary");

        if (data.status !== "OK") {
            throw new Error("Connectivity summary unavailable");
        }

        setText("connectivityTotal", data.total_settlements);
        setText("connectivityConnected", data.connected_settlements);
        setText("connectivityOutside", data.outside_largest_component);
        setText("connectivityStatus", "Scenario analysis loaded successfully.");
        setText("connectivityDisclaimer", data.interpretation);
    } catch (error) {
        console.error("Connectivity summary error:", error);
        setText("connectivityStatus", "Connectivity results unavailable.");
    }
}

// ======================================================
// RESPONSE DECISION ENGINE
// ======================================================

async function loadResponseDecisions() {
    const tbody = document.getElementById("decisionTableBody");
    if (!tbody) return;

    try {
        const data = await fetchJSON("/api/response-decisions");
        const summary = data.summary || {};
        const decisions = Array.isArray(data.decisions) ? data.decisions : [];
        const priorityCounts = summary.priority_counts || {};
        const connectivityCounts = summary.connectivity_counts || {};

        setText(
            "decisionReportStatus",
            `Response report loaded: ${data.generated_at_utc || "timestamp unavailable"}.`
        );
        setText(
            "decisionTotal",
            formatNumber(summary.settlements_assessed ?? decisions.length)
        );
        setText("decisionCritical", formatNumber(priorityCounts.CRITICAL || 0));
        setText(
            "decisionDisconnected",
            formatNumber(connectivityCounts["POTENTIALLY DISCONNECTED"] || 0)
        );
        setText("decisionUnknown", formatNumber(connectivityCounts.UNKNOWN || 0));

        tbody.replaceChildren();

        if (!decisions.length) {
            const row = tbody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 5;
            cell.textContent =
                "No response decisions available. Run the response decision engine first.";
            return;
        }

        for (const item of decisions) {
            const row = tbody.insertRow();

            row.insertCell().textContent =
                item.settlement || "Unnamed settlement";

            const priorityCell = row.insertCell();
            const level = String(item.priority_level || "UNKNOWN").toUpperCase();
            const badge = document.createElement("span");
            badge.className = `priority-badge priority-${level.toLowerCase()}`;
            badge.textContent = level;
            priorityCell.appendChild(badge);

            const score = Number(item.rescue_score);
            row.insertCell().textContent =
                Number.isFinite(score) ? `${score.toFixed(1)}/100` : "N/A";

            row.insertCell().textContent =
                item.connectivity_status || "UNKNOWN";

            const reasons = Array.isArray(item.reasons)
                ? item.reasons.join("; ")
                : "No reason provided";

            const action = item.recommended_action ||
                "Verify conditions with local authorities.";

            row.insertCell().textContent =
                `${reasons}. Follow-up: ${action}`;
        }

        const limitations = Array.isArray(data.limitations)
            ? data.limitations.join(" ")
            : "Results require local verification.";

        setText("decisionDisclaimer", limitations);
    } catch (error) {
        console.error("Response decisions error:", error);
        setText(
            "decisionReportStatus",
            "Response report unavailable. Generate response_decision_report.json and check the Flask API route."
        );

        tbody.replaceChildren();
        const row = tbody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 5;
        cell.textContent = "Could not load response decisions.";
    }
}

// ======================================================
// EMERGENCY INSIGHT
// ======================================================

function updateEmergencyInsight() {
    setText(
        "insight",
        "FLOODRA has processed satellite-derived flood information, " +
        "road infrastructure and candidate settlement-risk locations. " +
        "Review critical and high-priority markers for further assessment. " +
        "These are model estimates and require ground verification."
    );
}

// ======================================================
// LAYER CONTROL
// ======================================================

function createLayerControl() {
    if (layerControlCreated) return;

    L.control.layers(null, {
        "🌊 Flood Area": floodLayer,
        "🚧 Road Risk": roadLayer,
        "⚠️ Isolation Risk": isolationLayer,
        "🚨 Rescue Priority": priorityLayer,
        "🔗 Connectivity Scenario": connectivityLayer
    }, {
        collapsed: false
    }).addTo(map);

    layerControlCreated = true;
}

// ======================================================
// INITIALIZATION AND REFRESH
// ======================================================

async function initializeDashboard() {
    const button = document.getElementById("refreshButton");

    if (button) button.disabled = true;

    try {
        await Promise.all([
            loadFloodOverlay(),
            loadRoads(),
            loadIsolation(),
            loadPriority(),
            calculateFloodExtent(),
            loadConnectivity()
        ]);

        await Promise.all([
            loadSummary(),
            loadAnalysisReport(),
            loadRoadRiskChart(),
            loadRescueTable(),
            loadConnectivitySummary(),
            loadResponseDecisions()
        ]);

        updateEmergencyInsight();
    } finally {
        if (button) button.disabled = false;
    }
}

document.getElementById("refreshButton")?.addEventListener("click", async () => {
    const button = document.getElementById("refreshButton");
    const originalText = button.textContent;

    button.textContent = "Refreshing...";
    try {
        await initializeDashboard();
        await loadModelValidation();
    } catch (error) {
        console.error("Dashboard refresh failed:", error);
    } finally {
        button.textContent = originalText;
    }
});

createLayerControl();
initializeDashboard();

async function loadModelValidation() {
    try {
        const data = await fetchJSON("/api/model-validation");

        if (data.status !== "OK" || !data.report) {
            throw new Error(data.message || "Validation report unavailable");
        }

        const report = data.report;
        const checks = Array.isArray(report.checks) ? report.checks : [];

        setText(
            "modelValidationStatus",
            `Overall status: ${report.overall_status || "UNKNOWN"}`
        );

        setText("validationFloodMask", report.flood_mask?.status || "N/A");
        setText(
            "validationSeverity",
            report.severity_raster?.status || "N/A"
        );
        setText(
            "validationAlignment",
            report.raster_alignment?.status || "N/A"
        );
        setText("validationChecks", checks.length);

        const list = document.getElementById("validationCheckList");

        if (list) {
            list.replaceChildren();

            checks.forEach(check => {
                const item = document.createElement("p");
                item.textContent = `${check.name}: ${check.status}`;
                list.appendChild(item);
            });
        }

        const limitations = Array.isArray(report.limitations)
            ? report.limitations.join(" ")
            : "Independent validation is still required.";

        setText("validationDisclaimer", limitations);

    } catch (error) {
        console.error("Model validation error:", error);
        setText(
            "modelValidationStatus",
            "Validation report unavailable. Generate the report and check the API."
        );
    }
}
