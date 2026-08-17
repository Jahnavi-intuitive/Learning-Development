from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import verification

# Create tables on startup. Fine for local dev with SQLite; once you move to
# Postgres, replace this with a real migration tool (Alembic) so schema
# changes are tracked instead of implicit.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="L&D Agent - Certificate Verification Service",
    description=(
        "Deterministic verification engine (BRD Phase 3 / FR-3.1-3.4). "
        "No LLM anywhere in this service by design -- see Tech Stack doc Section 3."
    ),
    version="0.1.0",
)

app.include_router(verification.router, tags=["verification"])


@app.get("/health")
def health():
    return {"status": "ok"}


# Local admin/test UI (dev-only -- see README Section on the UI). Mounted last
# so it doesn't shadow the API routes above. Visit http://127.0.0.1:8000/ui/
# NOTE: use pathlib, not string-splitting on "/" -- __file__ uses backslashes
# on Windows, so a naive rsplit("/", 1) silently produces a nonexistent path there.
static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

# Privacy policy / terms of use for the Teams app registration (dev-only
# test app, see static/legal/*.html). Visit /legal/privacy-policy.html and
# /legal/terms-of-use.html.
app.mount("/legal", StaticFiles(directory=static_dir / "legal", html=True), name="legal")

# Downloadable Teams sideload package (dev-only, see static/package/*.zip).
app.mount("/package", StaticFiles(directory=static_dir / "package"), name="package")
