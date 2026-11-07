"""ASRA backend entry point.

This is the file uvicorn loads. It creates the FastAPI application object,
configures cross-origin access for the Next.js frontend, and mounts the
routes defined in the `api` package.

Run from Backend/:
    uvicorn main:app --reload --port 8000

`--reload` restarts the server whenever a Python file changes (dev only).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# All HTTP routes live in api/routes.py and are re-exported by api/__init__.py.
# Keeping routes out of this file means main.py only ever does wiring.
from api import router as api_router

# The application object. `title` and `description` show up in the
# auto-generated docs at http://localhost:8000/docs.
app = FastAPI(title="ASRA", description="Across-Species Risk Assessment")

# CORS (Cross-Origin Resource Sharing): browsers block a page on one origin
# (localhost:3000, the Next.js dev server) from calling an API on another
# origin (localhost:8000) unless the API explicitly allows it. This middleware
# adds the headers that grant that permission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server; add the deployed URL later
    allow_credentials=True,  # allow cookies/auth headers if we ever need them
    allow_methods=["*"],  # GET, POST, etc.
    allow_headers=["*"],  # e.g. Content-Type: application/json
)

# Attach every route from api/routes.py to the app (no URL prefix).
app.include_router(api_router)
