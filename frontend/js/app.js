const API_URL = "http://127.0.0.1:8000";

const uploadButton = document.getElementById("uploadButton");
const portfolioFile = document.getElementById("portfolioFile");
const uploadStatus = document.getElementById("uploadStatus");
const portfolioSection = document.getElementById("portfolioSection");
const portfolioValue = document.getElementById("portfolioValue");
const holdingCount = document.getElementById("holdingCount");
const holdingsTable = document.getElementById("holdingsTable");

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

        uploadStatus.textContent = "Portfolio uploaded successfully.";

    } catch (error) {
        console.error(error);
        uploadStatus.textContent = "Something went wrong.";
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