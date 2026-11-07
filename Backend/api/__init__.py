"""The `api` package: HTTP layer of the backend.

Re-exports the router so main.py can do `from api import router`
without knowing which file the routes live in.
"""

from api.routes import router

# Explicit public surface of the package.
__all__ = ["router"]
