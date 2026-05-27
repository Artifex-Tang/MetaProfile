"""Session dependency shim — re-exports fastapi_session_dep as get_db."""
from metaprofile.shared.db.postgres import fastapi_session_dep as get_db

__all__ = ["get_db"]
