// =========================================================
// VOLAREN — PORTFOLIO INTELLIGENCE
// Frontend Application
// =========================================================

const API_URL = "http://127.0.0.1:8000";


// =========================================================
// DOM ELEMENTS
// =========================================================

const uploadButton = document.getElementById("uploadButton");
const portfolioFile = document.getElementById("portfolioFile");
const uploadStatus = document.getElementById("uploadStatus");

const portfolioSection = document.getElementById("portfolioSection");

const portfolioValue = document.getElementById("portfolioValue");
const holdingCount = document.getElementById("holdingCount");
const holdingsTable = document.getElementById("holdingsTable");

const changesContent = document.getElementById("changesContent");

const historySummary = document.getElementById("historySummary");
const portfolioHistoryChart =
    document.getElementById("portfolioHistoryChart");

const whyHeadline = document.getElementById("whyHeadline");
const whyExplanation = document.getElementById("whyExplanation");
const whyContributors = document.getElementById("whyContributors");
const whyDetractors = document.getElementById("whyDetractors");
const whySectors = document.getElementById("whySectors");

const whyToggleButtons = document.querySelectorAll(".why-toggle-btn");


// =========================================================
// STATE
// =========================================================

let historyChart = null;
let currentPortfolioId = null;
let currentWhyMode = "brief"; // "brief" | "ai"


// =========================================================
// INITIALIZATION
// =========================================================

document.addEventListener("DOMContentLoaded", () => {

    if (uploadButton) {
        uploadButton.addEventListener("click", uploadPortfolio);
    }

    if (portfolioFile) {
        portfolioFile.addEventListener("change", handleFileSelection);
    }

    whyToggleButtons.forEach(btn => {
        btn.addEventListener("click", handleWhyToggle);
    });
});


// =========================================================
// WHY CARD TOGGLE
// =========================================================

function handleWhyToggle(event) {

    const btn = event.currentTarget;
    const mode = btn.dataset.mode;

    if (mode === currentWhyMode) {
        return;
    }

    currentWhyMode = mode;

    whyToggleButtons.forEach(b => {
        const isActive = b.dataset.mode === mode;
        b.classList.toggle("active", isActive);
        b.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    if (currentPortfolioId) {
        loadWhyCard(currentPortfolioId);
    }
}


// =========================================================
// FILE SELECTION
// =========================================================

function handleFileSelection() {

    const file = portfolioFile.files[0];

    if (!file) {
        uploadStatus.textContent = "";
        return;
    }

    if (!file.name.toLowerCase().endsWith(".csv")) {
        uploadStatus.textContent = "Please select a CSV file.";
        uploadStatus.className = "status-error";
        return;
    }

    uploadStatus.textContent = `Selected: ${file.name}`;
    uploadStatus.className = "status-success";
}


// =========================================================
// UPLOAD PORTFOLIO
// =========================================================

async function uploadPortfolio() {

    const file = portfolioFile.files[0];

    if (!file) {
        uploadStatus.textContent = "Please select a CSV file.";
        uploadStatus.className = "status-error";
        return;
    }

    if (!file.name.toLowerCase().endsWith(".csv")) {
        uploadStatus.textContent = "Only CSV files are supported.";
        uploadStatus.className = "status-error";
        return;
    }

    setUploadLoading(true);

    uploadStatus.textContent = "Uploading portfolio...";
    uploadStatus.className = "status-loading";

    const formData = new FormData();
    formData.append("file", file);

    try {

        const response = await fetch(
            `${API_URL}/api/portfolio/upload`,
            {
                method: "POST",
                body: formData
            }
        );

        if (!response.ok) {

            let message = "Upload failed.";

            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    message = errorData.detail;
                }
            } catch (_) {
                // Ignore JSON parse errors.
            }

            throw new Error(message);
        }

        const data = await response.json();

        currentPortfolioId = data.portfolio_id;

        renderPortfolio(data);

        await loadChanges(data.portfolio_id);
        await loadPortfolioHistory(data.portfolio_id);
        await loadWhyCard(data.portfolio_id);

        uploadStatus.textContent = "Portfolio uploaded successfully.";
        uploadStatus.className = "status-success";

    } catch (error) {

        console.error("Portfolio upload error:", error);

        uploadStatus.textContent = error.message || "Something went wrong.";
        uploadStatus.className = "status-error";

    } finally {
        setUploadLoading(false);
    }
}


// =========================================================
// UPLOAD BUTTON LOADING STATE
// =========================================================

function setUploadLoading(isLoading) {

    if (!uploadButton) return;

    uploadButton.disabled = isLoading;

    if (isLoading) {
        uploadButton.dataset.originalText = uploadButton.innerHTML;
        uploadButton.innerHTML = `
            <span class="button-loading">
                Analyzing...
            </span>
        `;
    } else {
        uploadButton.innerHTML = `
            Analyze Portfolio
            <span>→</span>
        `;
    }
}


// =========================================================
// LOAD WHAT CHANGED
// =========================================================

async function loadChanges(portfolioId) {

    if (!changesContent) return;

    changesContent.innerHTML = `
        <p class="changes-empty">
            Loading portfolio changes...
        </p>
    `;

    try {

        const response = await fetch(
            `${API_URL}/api/portfolio/${portfolioId}/changes`
        );

        if (response.status === 404) {
            changesContent.innerHTML = `
                <p class="changes-empty">
                    No previous snapshot to compare.
                </p>
            `;
            return;
        }

        if (!response.ok) {
            throw new Error(`Changes request failed (${response.status})`);
        }

        const diff = await response.json();
        renderChanges(diff);

    } catch (error) {

        console.error("Changes error:", error);

        changesContent.innerHTML = `
            <p class="changes-empty">
                Could not load portfolio changes.
            </p>
        `;
    }
}


// =========================================================
// LOAD PORTFOLIO HISTORY
// =========================================================

async function loadPortfolioHistory(portfolioId) {

    try {

        const response = await fetch(
            `${API_URL}/api/portfolio/${portfolioId}/history`
        );

        if (!response.ok) {
            throw new Error(`History request failed (${response.status})`);
        }

        const data = await response.json();
        renderHistory(data);

    } catch (error) {

        console.error("History error:", error);

        if (historySummary) {
            historySummary.innerHTML = `
                <span class="delta-negative">
                    History unavailable
                </span>
            `;
        }
    }
}


// =========================================================
// WHY DID MY PORTFOLIO MOVE? — LOADER
// =========================================================

async function loadWhyCard(portfolioId) {

    // Choose the explanation endpoint based on current mode
    const explainUrl = currentWhyMode === "ai"
        ? `${API_URL}/api/portfolio/${portfolioId}/explain/agent`
        : `${API_URL}/api/portfolio/${portfolioId}/explain`;

    const explainMethod = currentWhyMode === "ai" ? "POST" : "GET";

    // Disable toggle buttons while loading
    whyToggleButtons.forEach(b => { b.disabled = true; });

    try {

        const [explainRes, moversRes, attribRes] = await Promise.all([
            fetch(explainUrl, { method: explainMethod }),
            fetch(`${API_URL}/api/portfolio/${portfolioId}/movers`),
            fetch(`${API_URL}/api/portfolio/${portfolioId}/attribution`),
        ]);

        if (!explainRes.ok || !moversRes.ok || !attribRes.ok) {
            throw new Error("Why-card fetch failed");
        }

        const explain = await explainRes.json();
        const movers = await moversRes.json();
        const attribution = await attribRes.json();

        renderWhyCard(explain, movers, attribution);

    } catch (error) {

        console.error("Why card error:", error);

        if (whyExplanation) {
            whyExplanation.textContent =
                "Could not load portfolio attribution.";
        }

    } finally {

        // Re-enable toggle buttons
        whyToggleButtons.forEach(b => { b.disabled = false; });
    }
}


// =========================================================
// RENDER PORTFOLIO
// =========================================================

function renderPortfolio(data) {

    if (!portfolioSection) return;

    portfolioSection.classList.remove("hidden");

    const portfolio = data.portfolio || {};
    const holdings = Array.isArray(data.holdings) ? data.holdings : [];

    if (portfolioValue) {
        portfolioValue.textContent =
            formatCurrency(portfolio.portfolio_value || 0);
    }

    if (holdingCount) {
        holdingCount.textContent = holdings.length;
    }

    if (!holdingsTable) return;

    holdingsTable.innerHTML = "";

    if (!holdings.length) {
        holdingsTable.innerHTML = `
            <tr>
                <td colspan="9">No holdings found.</td>
            </tr>
        `;
        return;
    }

    holdings.forEach(holding => {

        const row = document.createElement("tr");

        const ticker = escapeHTML(holding.ticker || "-");
        const shares = Number(holding.shares || 0);
        const avgPrice = Number(holding.avg_price || 0);
        const currentPrice = Number(holding.current_price || 0);
        const positionValue = Number(holding.position_value || 0);
        const returnPct = Number(holding.return_pct || 0);
        const weightPct = Number(holding.weight_pct || 0);
        const contributionPct = Number(holding.contribution_pct || 0);
        const pnl = Number(holding.pnl || 0);

        row.innerHTML = `
            <td><strong>${ticker}</strong></td>
            <td>${formatNumber(shares)}</td>
            <td>${formatCurrency(avgPrice)}</td>
            <td>${formatCurrency(currentPrice)}</td>
            <td>${formatCurrency(positionValue)}</td>
            <td class="${deltaClass(returnPct)}">${formatPct(returnPct)}</td>
            <td>${formatPct(weightPct)}</td>
            <td class="${deltaClass(contributionPct)}">${formatPct(contributionPct)}</td>
            <td class="${deltaClass(pnl)}">${formatCurrencyWithSign(pnl)}</td>
        `;

        holdingsTable.appendChild(row);
    });
}


// =========================================================
// RENDER WHAT CHANGED
// =========================================================

function renderChanges(diff) {

    if (!changesContent) return;

    if (!diff || typeof diff !== "object") {
        changesContent.innerHTML = `
            <p class="changes-empty">No change data available.</p>
        `;
        return;
    }

    const parts = [];

    const valueBefore = Number(diff.portfolio_value_before || 0);
    const valueAfter = Number(diff.portfolio_value_after || 0);
    const valueDelta = Number(diff.portfolio_value_delta || 0);
    const returnBefore = Number(diff.return_pct_before || 0);
    const returnAfter = Number(diff.return_pct_after || 0);
    const returnDelta = Number(diff.return_pct_delta || 0);

    parts.push(`
        <div class="changes-summary">
            <div class="changes-summary-item">
                <span>Portfolio value</span>
                <strong>
                    ${formatCurrency(valueBefore)}
                    <span class="change-arrow">→</span>
                    ${formatCurrency(valueAfter)}
                    <em class="${deltaClass(valueDelta)}">
                        (${formatDeltaCurrency(valueDelta)})
                    </em>
                </strong>
            </div>
            <div class="changes-summary-item">
                <span>Return</span>
                <strong>
                    ${formatPct(returnBefore)}
                    <span class="change-arrow">→</span>
                    ${formatPct(returnAfter)}
                    <em class="${deltaClass(returnDelta)}">
                        (${formatDeltaPct(returnDelta)})
                    </em>
                </strong>
            </div>
        </div>
    `);

    const weightChanges = Array.isArray(diff.weight_changes) ? diff.weight_changes : [];
    if (weightChanges.length) {
        parts.push('<h3 class="changes-heading">Weight shifts</h3>');
        parts.push('<ul class="changes-list">');
        weightChanges.slice(0, 5).forEach(change => {
            const ticker = escapeHTML(change.ticker || "-");
            const before = Number(change.weight_before_pct || 0);
            const after = Number(change.weight_after_pct || 0);
            const delta = Number(change.weight_delta_pct || 0);
            parts.push(`
                <li>
                    <span class="changes-ticker">${ticker}</span>
                    <span class="changes-values">
                        ${formatPct(before)} <span class="change-arrow">→</span> ${formatPct(after)}
                    </span>
                    <em class="${deltaClass(delta)}">${formatDeltaPct(delta)}</em>
                </li>
            `);
        });
        parts.push('</ul>');
    }

    const contributionChanges = Array.isArray(diff.contribution_changes) ? diff.contribution_changes : [];
    if (contributionChanges.length) {
        parts.push('<h3 class="changes-heading">Contribution shifts</h3>');
        parts.push('<ul class="changes-list">');
        contributionChanges.slice(0, 5).forEach(change => {
            const ticker = escapeHTML(change.ticker || "-");
            const before = Number(change.contribution_before_pct || 0);
            const after = Number(change.contribution_after_pct || 0);
            const delta = Number(change.contribution_delta_pct || 0);
            parts.push(`
                <li>
                    <span class="changes-ticker">${ticker}</span>
                    <span class="changes-values">
                        ${formatPct(before)} <span class="change-arrow">→</span> ${formatPct(after)}
                    </span>
                    <em class="${deltaClass(delta)}">${formatDeltaPct(delta)}</em>
                </li>
            `);
        });
        parts.push('</ul>');
    }

    const newPositions = Array.isArray(diff.new_positions) ? diff.new_positions : [];
    if (newPositions.length) {
        const formattedPositions = newPositions.map(p => escapeHTML(p)).join(", ");
        parts.push(`
            <p class="changes-line">
                <strong>New positions:</strong> ${formattedPositions}
            </p>
        `);
    }

    const closedPositions = Array.isArray(diff.closed_positions) ? diff.closed_positions : [];
    if (closedPositions.length) {
        const formattedPositions = closedPositions.map(p => escapeHTML(p)).join(", ");
        parts.push(`
            <p class="changes-line">
                <strong>Closed positions:</strong> ${formattedPositions}
            </p>
        `);
    }

    if (parts.length === 1) {
        parts.push('<p class="changes-empty">No significant changes detected.</p>');
    }

    changesContent.innerHTML = parts.join("");
}


// =========================================================
// RENDER WHY CARD
// =========================================================

function renderWhyCard(explain, movers, attribution) {

    if (whyHeadline) {
        whyHeadline.textContent = explain.headline || "";
    }

    if (whyExplanation) {

        const source = explain.source || "deterministic";

        const sourceLabel =
            source === "llm"
                ? "AI-generated"
                : source === "deterministic_fallback"
                    ? "Deterministic (fallback)"
                    : "Deterministic";

        const sourceClass =
            source === "llm"
                ? "why-source-llm"
                : "why-source-deterministic";

        whyExplanation.innerHTML = `
            <span>${escapeHTML(explain.explanation || "")}</span>
            <br>
            <span class="why-source-badge ${sourceClass}">
                ${sourceLabel}
            </span>
        `;
    }

    if (whyContributors) {
        whyContributors.innerHTML = "";
        const contributors = movers.top_contributors || [];
        if (!contributors.length) {
            whyContributors.innerHTML = '<li class="changes-empty">No positive contributors.</li>';
        } else {
            contributors.forEach(h => {
                const li = document.createElement("li");
                li.innerHTML = `
                    <span class="why-list-ticker">${escapeHTML(h.ticker)}</span>
                    <span class="why-list-value delta-positive">${formatPct(h.contribution_pct)}</span>
                `;
                whyContributors.appendChild(li);
            });
        }
    }

    if (whyDetractors) {
        whyDetractors.innerHTML = "";
        const detractors = movers.top_detractors || [];
        if (!detractors.length) {
            whyDetractors.innerHTML = '<li class="changes-empty">No negative detractors.</li>';
        } else {
            detractors.forEach(h => {
                const li = document.createElement("li");
                li.innerHTML = `
                    <span class="why-list-ticker">${escapeHTML(h.ticker)}</span>
                    <span class="why-list-value delta-negative">${formatPct(h.contribution_pct)}</span>
                `;
                whyDetractors.appendChild(li);
            });
        }
    }

    if (whySectors) {
        whySectors.innerHTML = "";
        const sectors = attribution.sectors || [];
        if (!sectors.length) {
            whySectors.innerHTML = `
                <tr><td colspan="5" class="changes-empty">No sector data available.</td></tr>
            `;
        } else {
            sectors.forEach(sector => {
                const row = document.createElement("tr");
                const tickers = (sector.holdings || []).map(escapeHTML).join(", ");
                const contribution = Number(sector.contribution_pct || 0);
                const cls = contribution > 0
                    ? "delta-positive"
                    : contribution < 0
                        ? "delta-negative"
                        : "delta-neutral";
                row.innerHTML = `
                    <td>${escapeHTML(sector.sector)}</td>
                    <td>${formatPct(sector.weight_pct)}</td>
                    <td>${formatPct(sector.return_pct)}</td>
                    <td class="${cls}">${formatPct(contribution)}</td>
                    <td>${tickers}</td>
                `;
                whySectors.appendChild(row);
            });
        }
    }
}


// =========================================================
// RENDER HISTORY
// =========================================================

function renderHistory(data) {

    const history = Array.isArray(data?.history) ? data.history : [];
    const summary = data?.summary || {};

    if (historySummary) {
        const totalReturn = Number(summary.total_return_pct || 0);
        const sign = totalReturn > 0 ? "+" : "";
        historySummary.innerHTML = `
            <strong>${formatCurrency(summary.current_value || 0)}</strong>
            <br>
            <span class="${deltaClass(totalReturn)}">
                ${sign}${totalReturn.toFixed(2)}%
            </span>
            <span>since first snapshot</span>
            <span>(${Number(summary.snapshot_count || 0)} snapshots)</span>
        `;
    }

    if (!history.length) {
        destroyHistoryChart();
        return;
    }

    const labels = history.map(s => formatDate(s.created_at));
    const values = history.map(s => Number(s.portfolio_value || 0));

    const canvas = document.getElementById("portfolioHistoryChart");
    if (!canvas) return;

    destroyHistoryChart();

    if (typeof Chart === "undefined") {
        console.error("Chart.js is not loaded.");
        return;
    }

    historyChart = new Chart(canvas, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Portfolio Value",
                data: values,
                tension: 0.3,
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                borderColor: "#111111",
                backgroundColor: "rgba(255, 90, 31, 0.08)",
                pointBackgroundColor: "#ff5a1f",
                pointBorderColor: "#ffffff",
                pointBorderWidth: 2,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            animation: { duration: 700, easing: "easeOutQuart" },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#111111",
                    titleColor: "#ffffff",
                    bodyColor: "#ffffff",
                    borderColor: "#ff5a1f",
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            return " Value: " + formatCurrency(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#737373" } },
                y: {
                    beginAtZero: false,
                    grid: { color: "#eeeeee" },
                    ticks: {
                        color: "#737373",
                        callback: function(value) { return formatCurrency(value); }
                    }
                }
            }
        }
    });
}


// =========================================================
// DESTROY HISTORY CHART
// =========================================================

function destroyHistoryChart() {
    if (historyChart) {
        historyChart.destroy();
        historyChart = null;
    }
}


// =========================================================
// FORMATTERS
// =========================================================

function deltaClass(value) {
    const number = Number(value) || 0;
    if (number > 0) return "delta-positive";
    if (number < 0) return "delta-negative";
    return "delta-neutral";
}

function formatDeltaCurrency(value) {
    const number = Number(value) || 0;
    const sign = number > 0 ? "+" : "";
    return `${sign}${formatCurrency(number)}`;
}

function formatDeltaPct(value) {
    const number = Number(value) || 0;
    const sign = number > 0 ? "+" : "";
    return `${sign}${number.toFixed(2)}%`;
}

function formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2
    }).format(Number(value) || 0);
}

function formatCurrencyWithSign(value) {
    const number = Number(value) || 0;
    const sign = number > 0 ? "+" : "";
    return `${sign}${formatCurrency(number)}`;
}

function formatPct(value) {
    const number = Number(value) || 0;
    const sign = number >= 0 ? "+" : "";
    return `${sign}${number.toFixed(2)}%`;
}

function formatNumber(value) {
    const number = Number(value) || 0;
    return new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 4
    }).format(number);
}

function formatDate(dateString) {
    if (!dateString) return "-";
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}