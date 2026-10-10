import os
import tempfile

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException
)

from app.services.portfolio_service import (
    read_portfolio_csv,
    calculate_position_values,
    calculate_portfolio_value
)


router = APIRouter(
    prefix="/api/portfolio",
    tags=["Portfolio"]
)


@router.post("/upload")
async def upload_portfolio(
    file: UploadFile = File(...)
):

    if not file.filename.endswith(".csv"):

        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    contents = await file.read()

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".csv"
    ) as temp_file:

        temp_file.write(contents)
        temp_path = temp_file.name

    try:

        df = read_portfolio_csv(temp_path)

        df = calculate_position_values(df)

        portfolio_value = calculate_portfolio_value(df)

        holdings = df.to_dict(orient="records")

        return {
            "portfolio_value": portfolio_value,
            "holdings": holdings
        }

    finally:

        os.unlink(temp_path)
