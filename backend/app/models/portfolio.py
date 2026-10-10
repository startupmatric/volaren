from pydantic import BaseModel
from typing import List

from .holding import Holding


class Portfolio(BaseModel):

    name: str
    holdings: List[Holding]
