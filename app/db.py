"""
Legacy compatibility module.

The canonical database layer is `app.database`.
The old SQLite/SQLModel prototype was retired to avoid conflicts with
Master_Prompt_v1.0 and the PostgreSQL-based architecture.
"""

from app.database import Base, async_session_factory, engine, get_db

__all__ = ["Base", "async_session_factory", "engine", "get_db"]
