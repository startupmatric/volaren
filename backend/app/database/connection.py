# Kept for backward compatibility with Day 1 imports.
# New code should import from app.database.session instead.

from app.database.session import (  # noqa: F401
    DATABASE_URL,
    SessionLocal,
    engine,
    get_db,
)