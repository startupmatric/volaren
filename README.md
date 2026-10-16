# Volaren — Portfolio Intelligence

> Understand **why your portfolio moved**, not just how much it moved.

Volaren is a portfolio intelligence platform that combines deterministic financial analytics, historical portfolio analysis, grounded LLM reasoning, evaluation, and MCP-based tool access.

The core question is simple:

**“Why did my portfolio move?”**

## 🚀 What Volaren Does

| Capability | Description |
|---|---|
| Portfolio ingestion | Upload portfolio snapshots through CSV |
| Performance analytics | Calculate value, P&L, returns, weights, and contribution |
| Snapshot persistence | Store portfolio history in PostgreSQL |
| What Changed? | Compare the latest snapshot with the previous snapshot |
| Historical analysis | Track portfolio value and returns over time |
| Movers | Identify largest contributors and drags |
| Sector attribution | Understand which sectors drove performance |
| Root-cause explanation | Generate deterministic explanations |
| AI explanation | Use LangGraph + LLM to explain structured evidence |
| Evaluation | Measure grounding, ticker accuracy, and fact coverage |
| MCP | Expose portfolio intelligence as agent-accessible tools |

# 🧠 Architecture

```text
                    ┌──────────────────────┐
                    │     CSV Portfolio    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       FastAPI        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     PostgreSQL       │
                    │ Portfolios/Snapshots │
                    │      /Holdings       │
                    └──────────┬───────────┘
                               │
                               ▼
             ┌──────────────────────────────────┐
             │     Deterministic Analytics       │
             │                                  │
             │  • Performance                   │
             │  • Attribution                   │
             │  • Movers                        │
             │  • Sector Analysis               │
             │  • Snapshot Diffs                │
             │  • Historical Analysis            │
             └────────────────┬─────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │      LangGraph       │
                    │                      │
                    │ prepare_context      │
                    │       ↓              │
                    │ reason               │
                    │       ↓              │
                    │ validate             │
                    │       ↓              │
                    │ finalize             │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Grounded LLM      │
                    │    Explanation       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Evaluation Harness   │
                    │ • Grounding          │
                    │ • Ticker accuracy    │
                    │ • Fact coverage      │
                    └──────────────────────┘


                    MCP Integration
                           │
                           ▼
                 ┌──────────────────────┐
                 │    MCP Server        │
                 │                      │
                 │ get_portfolio        │
                 │ get_changes          │
                 │ get_history          │
                 │ get_movers           │
                 │ get_sectors          │
                 └──────────────────────┘
```

# 🔑 Core Engineering Principle

## The LLM does not calculate financial numbers.

All important financial calculations are performed deterministically using Python and database-backed services.

The LLM receives structured evidence such as:

```python
{
    "portfolio_return": 3.24,
    "top_gainer": "NVDA",
    "top_gainer_contribution": 2.10,
    "top_loser": "GOOGL",
    "top_loser_contribution": -0.31,
    "leading_sector": "Semiconductors"
}
```

The model's job is to explain those facts in natural language.

```text
Financial Truth
      ↓
Deterministic Analytics
      ↓
Structured Evidence
      ↓
LLM Reasoning
      ↓
Validated Explanation
```

# 📅 Development Progress

## Day 1 — Portfolio Foundation

- CSV upload
- Portfolio ingestion
- FastAPI backend
- PostgreSQL
- Docker
- Holdings dashboard

## Day 2 — Performance & Attribution

Added:

- Current value
- Cost basis
- P&L
- Return %
- Portfolio weight
- Contribution to portfolio return

## Day 3 — Persistence & What Changed?

Introduced persistent portfolio snapshots.

```text
Portfolio
   │
   └── Snapshot
          │
          └── Holdings
```

Implemented:

- Portfolio persistence
- Snapshot persistence
- Holding persistence
- New positions
- Closed positions
- Weight changes
- Contribution changes
- Portfolio-level changes

## Day 4 — Historical Intelligence

Added:

- Snapshot history
- Portfolio value history
- Return history
- Historical API
- Chart.js visualization
- Snapshot timeline

## Day 5 — Root-Cause Intelligence

Added:

### Movers
Identifies the largest contributors and drags.

### Sector attribution
Determines which sectors contributed most to portfolio performance.

### Root-cause explanation
Generates deterministic explanations answering what drove portfolio movement.

## Day 6 — LangGraph + LLM

Introduced a LangGraph reasoning layer:

```text
Portfolio Facts
      ↓
prepare_context
      ↓
reason
      ↓
validate
      ↓
finalize
```

The LLM receives structured portfolio evidence rather than raw database access.

## Day 7 — Agent Evaluation Harness

Added an evaluation layer for AI reliability.

Components:

```text
evaluation/
├── datasets.py
├── validators.py
├── evaluator.py
└── harness.py
```

Measures:

- Number grounding
- Ticker accuracy
- Fact coverage

Current status:

**73 tests passing**

## Day 8 — MCP Integration

Portfolio intelligence capabilities are exposed through MCP.

Available capabilities include:

```text
get_portfolio_summary
get_portfolio_changes
get_portfolio_history
get_portfolio_movers
get_portfolio_sectors
```

Architecture:

```text
External Agent
      ↓
     MCP
      ↓
Volaren Portfolio Tools
      ↓
Existing Analytics Services
      ↓
PostgreSQL
```

The MCP layer remains thin and reuses existing business logic.

# 🧪 Evaluation Philosophy

AI systems should not be evaluated only by whether the output sounds good.

Volaren evaluates whether the explanation is actually supported by the underlying evidence.

Example:

```text
Actual:
NVDA contribution = +2.10pp

LLM:
NVDA contributed +5.40pp
```

The response may sound convincing, but the evaluator should fail it.

```text
Input
 ↓
Agent
 ↓
Output
 ↓
Validation
 ↓
Evaluation
 ↓
PASS / FAIL
```

# 🛠️ Tech Stack

## Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pandas
- Pydantic

## AI

- LangGraph
- OpenAI-compatible LLM integration
- Grounded reasoning
- Evaluation harness

## Agent Infrastructure

- MCP
- Tool-based agent architecture
- Structured tool outputs

## Frontend

- HTML
- CSS
- JavaScript
- Chart.js

## Infrastructure

- Docker
- Docker Compose
- PostgreSQL 16

## Testing

- Pytest
- Golden datasets
- Deterministic validators
- Evaluation harness

# 📂 Project Structure

```text
volaren-portfolio-intelligence/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── evaluation/
│   │   ├── models/
│   │   ├── services/
│   │   └── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
│
├── mcp_server/
│   ├── server.py
│   └── ...
│
├── data/
│   ├── demo_portfolio.csv
│   └── demo_portfolio_v2.csv
│
├── tests/
│
├── Dockerfile
├── docker-compose.yml
├── .gitignore
└── README.md
```

# 🚀 Running Locally

## 1. Clone

```bash
git clone https://github.com/startupmatric/volaren.git
cd volaren
```

## 2. Configure environment

Create `.env`:

```env
OPENAI_API_KEY=your_key_here
```

Do not commit `.env`.

## 3. Start Docker

```bash
docker compose up -d --build
```

Check containers:

```bash
docker compose ps
```

## 4. API

FastAPI:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

# 🧪 Run Tests

```bash
docker compose exec -T backend pytest -q
```

Current project status:

```text
73 tests passing
```

# 🔌 MCP Server

Run the MCP development inspector:

```bash
mcp dev mcp_server/server.py
```

Available tools:

```text
get_portfolio_summary
get_portfolio_changes
get_portfolio_history
get_portfolio_movers
get_portfolio_sectors
```

The MCP server uses stdio and should be accessed through an MCP client such as an MCP Inspector or compatible agent client.

# 📡 API Capabilities

The application provides portfolio APIs for:

```text
Portfolio listing
Portfolio upload
Portfolio changes
Portfolio history
Portfolio movers
Sector attribution
Portfolio explanations
AI evaluation
Agent evaluation
```

See the live FastAPI Swagger documentation at:

```text
http://localhost:8000/docs
```

# 📊 Example Intelligence Output

```text
Portfolio Return: +3.24%

Largest Contributor:
NVDA +2.10pp

Largest Drag:
GOOGL -0.31pp

Leading Sector:
Semiconductors
```

The deterministic engine produces the evidence.

The AI layer turns that evidence into a concise explanation.

# 🧱 Design Principles

## 1. Deterministic first

Financial calculations should be reproducible.

```text
Python / SQL
     ↓
Facts
```

## 2. LLM as reasoning layer

The model transforms structured evidence into useful language.

It should not become the source of financial truth.

## 3. Evaluation is part of the system

Evaluation is not an afterthought.

```text
Input
 ↓
Agent
 ↓
Output
 ↓
Validation
 ↓
Evaluation
```

## 4. Thin MCP layer

MCP provides an interface for agents.

Business logic remains inside the existing services.

## 5. Build around the user question

The product is not:

> “An LLM that talks about portfolios.”

It is:

> **“An intelligence system that explains why a portfolio moved.”**

# 🔮 Roadmap

Potential future capabilities:

- Continuous evaluation and drift monitoring
- Snapshot drill-down
- Multi-portfolio management
- Portfolio comparison
- PDF/CSV intelligence reports
- Real-time market data
- News/event attribution
- Thesis-aware portfolio analysis
- Promoter intelligence for Indian equities
- Multi-tenant authentication
- Production observability
- Advanced MCP agent workflows

# 🎯 Product Vision

Volaren aims to move from:

```text
Portfolio Dashboard
```

to:

```text
Portfolio Intelligence
```

Instead of forcing investors to manually inspect:

```text
Prices
Holdings
Weights
Sectors
Transactions
News
```

the system should answer:

> **What changed?**

> **Why did it change?**

> **What caused the move?**

> **Does it matter?**

> **Does it affect my investment thesis?**

# 👨‍💻 Built By

**Yashwanth S**

AI Systems Engineer / Full-Stack Developer

GitHub: https://github.com/startupmatric

Portfolio: https://s-yashwnath-portfolio.vercel.app/

# 📜 Status

**Prototype / Active Development**

```text
Portfolio Analytics       ✅
Persistence               ✅
Snapshot Diff             ✅
Historical Analysis       ✅
Attribution               ✅
Root-Cause Explanation    ✅
LangGraph                 ✅
LLM Grounding             ✅
Evaluation Harness        ✅
Golden Dataset             ✅
MCP Integration           ✅
```

---

## ⭐ Engineering Principle

> **AI should explain data that the system can prove, rather than inventing the data it explains.**
