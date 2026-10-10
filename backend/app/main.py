from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.portfolio import router as portfolio_router


app = FastAPI(
    title="Volaren Portfolio Intelligence",
    description="Portfolio What Changed? prototype",
    version="0.1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(portfolio_router)


@app.get("/")
def root():

    return {
        "name": "Volaren Portfolio Intelligence",
        "status": "running",
        "version": "0.1.0"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }
