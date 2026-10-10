from pydantic import BaseModel


class Holding(BaseModel):

    ticker: str
    shares: float
    avg_price: float
    sector: str | None = None
