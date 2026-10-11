import os
import tempfile

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
    get_latest_snapshots,
    get_or_create_portfolio,
    list_portfolios,
    save_snapshot,
)
from app.services.diff_service import compute_diff
from app.services.history_service import (
    get_historical_summary,
    get_snapshot_history,
)


router = APIRouter(
    prefix="/api/portfolio",
    tags=["Portfolio"],
)


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