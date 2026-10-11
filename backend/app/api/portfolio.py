import os
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.portfolio_service import read_portfolio_csv
from app.services.performance_service import (
    calculate_performance,
    calculate_portfolio_metrics,
)


router = APIRouter(
    prefix="/api/portfolio",
    tags=["Portfolio"],
)


@router.post("/upload")
async def upload_portfolio(file: UploadFile = File(...)):

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
        holdings = df.to_dict(orient="records")

        return {
            "portfolio": metrics,
            "holdings": holdings,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        os.unlink(temp_path)