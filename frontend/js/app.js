const API_URL = "http://127.0.0.1:8000";

const uploadButton = document.getElementById("uploadButton");
const portfolioFile = document.getElementById("portfolioFile");
const uploadStatus = document.getElementById("uploadStatus");
const portfolioSection = document.getElementById("portfolioSection");
const portfolioValue = document.getElementById("portfolioValue");
const holdingCount = document.getElementById("holdingCount");
const holdingsTable = document.getElementById("holdingsTable");
const changesContent = document.getElementById("changesContent");

uploadButton.addEventListener("click", uploadPortfolio);

async function uploadPortfolio() {

    const file = portfolioFile.files[0];

    if (!file) {
        uploadStatus.textContent = "Please select a CSV file.";
        return;
    }

    uploadStatus.textContent = "Uploading...";

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
            throw new Error("Upload failed");
        }

        const data = await response.json();

        renderPortfolio(data);

        await loadChanges(data.portfolio_id);

        uploadStatus.textContent = "Portfolio uploaded successfully.";

    } catch (error) {
        console.error(error);
        uploadStatus.textContent = "Something went wrong.";
    }
}

async function loadChanges(portfolioId) {

    try {
        const response = await fetch(
            `${API_URL}/api/portfolio/${portfolioId}/changes`
        );

        if (response.status === 404) {
            changesContent.innerHTML =
                '<p class="changes-empty">No previous snapshot to compare.</p>';
            return;
        }

        if (!response.ok) {
            throw new Error("Changes fetch failed");
        }

        const diff = await response.json();
        renderChanges(diff);

    } catch (error) {
        console.error(error);
        changesContent.innerHTML =
            '<p class="changes-empty">Could not load changes.</p>';
    }
}

function renderPortfolio(data) {

    portfolioSection.classList.remove("hidden");

    const portfolio = data.portfolio || {};

    portfolioValue.textContent =
        formatCurrency(portfolio.portfolio_value || 0);

    holdingCount.textContent = data.holdings.length;

    holdingsTable.innerHTML = "";

    data.holdings.forEach(holding => {

        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${holding.ticker}</td>
            <td>${holding.shares}</td>
            <td>${formatCurrency(holding.avg_price)}</td>
            <td>${formatCurrency(holding.current_price)}</td>
            <td>${formatCurrency(holding.position_value)}</td>
            <td>${formatPct(holding.return_pct)}</td>
            <td>${formatPct(holding.weight_pct)}</td>
            <td>${formatPct(holding.contribution_pct)}</td>
            <td>${formatCurrency(holding.pnl)}</td>
        `;

        holdingsTable.appendChild(row);

    });
}

function renderChanges(diff) {

    const parts = [];

    parts.push(`
        <div class="changes-summary">
            <div class="changes-summary-item">
                <span>Portfolio value</span>
                <strong>
                    ${formatCurrency(diff.portfolio_value_before)}
                    → ${formatCurrency(diff.portfolio_value_after)}
                    <em class="${deltaClass(diff.portfolio_value_delta)}">
                        (${formatDeltaCurrency(diff.portfolio_value_delta)})
                    </em>
                </strong>
            </div>
            <div class="changes-summary-item">
                <span>Return</span>
                <strong>
                    ${formatPct(diff.return_pct_before)}
                    → ${formatPct(diff.return_pct_after)}
                    <em class="${deltaClass(diff.return_pct_delta)}">
                        (${formatDeltaPct(diff.return_pct_delta)})
                    </em>
                </strong>
            </div>
        </div>
    `);

    if (diff.weight_changes && diff.weight_changes.length) {
        parts.push('<h3 class="changes-heading">Weight shifts</h3>');
        parts.push('<ul class="changes-list">');
        diff.weight_changes.slice(0, 5).forEach(w => {
            parts.push(`
                <li>
                    <span class="changes-ticker">${w.ticker}</span>
                    <span class="changes-values">
                        ${formatPct(w.weight_before_pct)}
                        →
                        ${formatPct(w.weight_after_pct)}
                    </span>
                    <em class="${deltaClass(w.weight_delta_pct)}">
                        ${formatDeltaPct(w.weight_delta_pct)}
                    </em>
                </li>
            `);
        });
        parts.push('</ul>');
    }

    if (diff.contribution_changes && diff.contribution_changes.length) {
        parts.push('<h3 class="changes-heading">Contribution shifts</h3>');
        parts.push('<ul class="changes-list">');
        diff.contribution_changes.slice(0, 5).forEach(c => {
            parts.push(`
                <li>
                    <span class="changes-ticker">${c.ticker}</span>
                    <span class="changes-values">
                        ${formatPct(c.contribution_before_pct)}
                        →
                        ${formatPct(c.contribution_after_pct)}
                    </span>
                    <em class="${deltaClass(c.contribution_delta_pct)}">
                        ${formatDeltaPct(c.contribution_delta_pct)}
                    </em>
                </li>
            `);
        });
        parts.push('</ul>');
    }

    if (diff.new_positions && diff.new_positions.length) {
        parts.push(`
            <p class="changes-line">
                <strong>New positions:</strong>
                ${diff.new_positions.join(", ")}
            </p>
        `);
    }

    if (diff.closed_positions && diff.closed_positions.length) {
        parts.push(`
            <p class="changes-line">
                <strong>Closed positions:</strong>
                ${diff.closed_positions.join(", ")}
            </p>
        `);
    }

    changesContent.innerHTML = parts.join("");
}

function deltaClass(value) {
    const n = Number(value) || 0;
    if (n > 0) return "delta-positive";
    if (n < 0) return "delta-negative";
    return "delta-neutral";
}

function formatDeltaCurrency(value) {
    const n = Number(value) || 0;
    const sign = n > 0 ? "+" : "";
    return `${sign}${formatCurrency(n)}`;
}

function formatDeltaPct(value) {
    const n = Number(value) || 0;
    const sign = n > 0 ? "+" : "";
    return `${sign}${n.toFixed(2)}%`;
}

function formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2
    }).format(value);
}

function formatPct(value) {
    const n = Number(value) || 0;
    const sign = n >= 0 ? "+" : "";
    return `${sign}${n.toFixed(2)}%`;
}