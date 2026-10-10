# Volaren Portfolio Intelligence

Day 1 prototype: CSV → FastAPI → pandas → dashboard.

## Stack

- Backend: FastAPI + pandas + SQLAlchemy
- Frontend: HTML / CSS / JavaScript
- Database: PostgreSQL (Day 2 integration)
- Infra: Docker + Docker Compose

## Run

### Backend (local)

    cd backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

### Frontend (local)

    cd frontend
    python -m http.server 5500

### Docker

    docker compose up -d --build

- Swagger: http://localhost:8000/docs
- Dashboard: http://localhost:5500

## Endpoints

- GET /                           service info
- GET /health                     health check
- POST /api/portfolio/upload      upload CSV, returns portfolio value + holdings
