import os
import tempfile
from app.services.agent_explain_service import (
    explain_portfolio_with_agent,
)
from app.schemas.explanation import (
    AgentExplainResponse,
    EvaluationReport,
)
from app.agents.portfolio_agent import run_agent
from app.agents.tool_registry import INTENT_EXPLAIN_MOVEMENT
from app.services.evaluation_service import evaluate_portfolio
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.database.models import Snapshot
from app.database.session import get_db
from app.services.portfolio_service import read_portfolio_csv
from app.services.performance_service import (
    calculate_performance,
    calculate_portfolio_metrics,
)
from app.services.persistence_service import (
    get_or_create_portfolio,
    list_portfolios,
    save_snapshot,
)
from app.services.diff_service import compute_diff
from app.services.history_service import (
    get_historical_summary,
    get_snapshot_history,
)
from app.services.attribution_service import (
    get_movers,
    get_sector_attribution,
)
from app.services.explain_service import explain_attribution


router = APIRouter(
    prefix="/api/portfolio",
    tags=["Portfolio"],
)


# =========================================================
# UPLOAD
# =========================================================

@router.post("/upload")
async def upload_portfolio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported",
        )

    contents = await file.read()

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv"
    ) as temp_file:
        temp_file.write(contents)
        temp_path = temp_file.name

    try:
        df = read_portfolio_csv(temp_path)

        if "current_price" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Missing required column: current_price",
            )

        df = calculate_performance(df)
        metrics = calculate_portfolio_metrics(df)

        portfolio = get_or_create_portfolio(db, name="Default")
        snapshot = save_snapshot(
            db,
            portfolio_id=portfolio.id,
            metrics=metrics,
            df=df,
        )

        holdings = df.to_dict(orient="records")

        return {
            "portfolio_id": portfolio.id,
            "snapshot_id": snapshot.id,
            "portfolio": metrics,
            "holdings": holdings,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        os.unlink(temp_path)


# =========================================================
# LIST PORTFOLIOS
# =========================================================

@router.get("/")
def get_portfolios(db: Session = Depends(get_db)):
    portfolios = list_portfolios(db)

    return {
        "portfolios": [
            {
                "id": p.id,
                "name": p.name,
                "created_at": p.created_at,
                "snapshot_count": len(p.snapshots),
            }
            for p in portfolios
        ]
    }


# =========================================================
# SNAPSHOTS
# =========================================================

@router.get("/{portfolio_id}/snapshots")
def get_snapshots(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    snapshots = (
        db.query(Snapshot)
        .filter(Snapshot.portfolio_id == portfolio_id)
        .order_by(Snapshot.created_at.desc(), Snapshot.id.desc())
        .all()
    )

    return {
        "portfolio_id": portfolio_id,
        "snapshots": [
            {
                "id": s.id,
                "created_at": s.created_at,
                "portfolio_value": s.portfolio_value,
                "return_pct": s.return_pct,
            }
            for s in snapshots
        ],
    }


# =========================================================
# WHAT CHANGED (DIFF)
# =========================================================

@router.get("/{portfolio_id}/changes")
def get_changes(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    diff = compute_diff(db, portfolio_id)

    if diff is None:
        raise HTTPException(
            status_code=404,
            detail="Need at least 2 snapshots to compute changes",
        )

    return diff


# =========================================================
# HISTORY
# =========================================================

@router.get("/{portfolio_id}/history")
def get_portfolio_history(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    history = get_snapshot_history(db, portfolio_id)
    summary = get_historical_summary(db, portfolio_id)

    return {
        "portfolio_id": portfolio_id,
        "summary": summary,
        "history": history,
    }


# =========================================================
# MOVERS (Day 5)
# =========================================================

@router.get("/{portfolio_id}/movers")
def get_portfolio_movers(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    movers = get_movers(db, portfolio_id)

    if movers is None:
        raise HTTPException(
            status_code=404,
            detail="No snapshots found for this portfolio",
        )

    return movers


# =========================================================
# SECTOR ATTRIBUTION (Day 5)
# =========================================================

@router.get("/{portfolio_id}/attribution")
def get_portfolio_attribution(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    attribution = get_sector_attribution(db, portfolio_id)

    if attribution is None:
        raise HTTPException(
            status_code=404,
            detail="No snapshots found for this portfolio",
        )

    return attribution


# =========================================================
# EXPLAIN (Day 5)
# =========================================================

@router.get("/{portfolio_id}/explain")
def get_portfolio_explanation(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    explanation = explain_attribution(db, portfolio_id)

    if explanation is None:
        raise HTTPException(
            status_code=404,
            detail="No snapshots found for this portfolio",
        )

    return explanation
@router.post("/{portfolio_id}/explain/agent")
def get_portfolio_agent_explanation(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    """
    LLM-powered explanation of the latest snapshot.

    The numbers come from the deterministic attribution service.
    The LLM only writes prose. If the LLM invents a number, the
    agent's validation layer catches it and falls back to the
    deterministic explanation.
    """

    result = explain_portfolio_with_agent(db, portfolio_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No snapshots found for this portfolio",
        )

    # If the agent itself errored, surface a 500
    if result.get("source") == "error":
        raise HTTPException(
            status_code=500,
            detail="Agent failed to produce an explanation",
        )

    return result
# =========================================================
# EVALUATION (Day 7)
# =========================================================

@router.post(
    "/{portfolio_id}/evaluate",
    response_model=EvaluationReport,
)
def evaluate_portfolio_deterministic_endpoint(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluate the deterministic explanation of the latest snapshot.

    Runs in milliseconds. No LLM. Always available.
    Useful as a CI baseline and for regression testing.
    """

    report = evaluate_portfolio(
        db,
        portfolio_id,
        mode="deterministic",
    )

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No snapshots found for this portfolio",
        )

    return report


@router.post(
    "/{portfolio_id}/evaluate/agent",
    response_model=EvaluationReport,
)
def evaluate_portfolio_agent_endpoint(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluate the LLM explanation of the latest snapshot.

    Triggers a Groq API call (~2-5 seconds).
    Falls back to deterministic if the LLM fails; the fallback
    is reported with source='deterministic_fallback' and passed=False.
    """

    report = evaluate_portfolio(
        db,
        portfolio_id,
        mode="agent",
    )

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No snapshots found for this portfolio",
        )

    return report
# =========================================================
# TOOL-CALLING AGENT (Day 8a)
# =========================================================

@router.post(
    "/{portfolio_id}/explain/agent/v2",
    response_model=AgentExplainResponse,
)
def get_portfolio_agent_v2_explanation(
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    """
    Tool-calling agent explanation of the latest snapshot.

    Unlike `/explain/agent`, this endpoint uses the LangGraph
    tool-calling loop: the LLM decides which tools to call
    (movers, summary, sectors), sees their results, and writes
    the explanation from grounded data.

    Returns:
        - explanation
        - source ("llm" or "deterministic_fallback")
        - validation result (numbers grounded in evidence)
        - tool_calls: list of {name, args, latency_ms}
    """

    result = run_agent(
        db,
        portfolio_id,
        intent=INTENT_EXPLAIN_MOVEMENT,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No snapshots found for this portfolio",
        )

    return result