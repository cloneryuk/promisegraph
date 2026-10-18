from urllib.parse import urlparse
import hashlib
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import ROOT, Settings
from .graph import GraphRepository, DatabaseUnavailable, ReviewConflict
from .llm import ModelUnavailable
from .service import Service
from .schemas import DocumentInput, ReviewInput, AskInput, DemoInput
from .ingest import catalog
from .agent import run_agent
from .demo import examples, load_demo
from .security import DemoSecurityMiddleware, SecuritySettings


def get_service():
    return Service()


app = FastAPI(
    title="PromiseGraph",
    version="0.1.0",
    description="Evidence-backed commitment intelligence",
)
app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")


@app.middleware("http")
async def local_guard(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                {"detail": "Cross-origin writes are disabled."}, status_code=403
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(DatabaseUnavailable)
async def db_error(request, exc):
    return JSONResponse(
        {"detail": str(exc), "code": "database_unavailable"}, status_code=503
    )


@app.exception_handler(ModelUnavailable)
async def model_error(request, exc):
    return JSONResponse(
        {"detail": str(exc), "code": "model_unavailable"}, status_code=502
    )


@app.exception_handler(ReviewConflict)
async def review_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get("/", response_class=HTMLResponse)
def home():
    # A content-based URL changes on every asset edit, including local updates
    # whose file timestamps happen to match a previously cached response.
    assets = ROOT / "app/static"
    version = hashlib.sha256(
        (assets / "app.js").read_bytes() + (assets / "styles.css").read_bytes()
    ).hexdigest()[:12]
    return (
        (ROOT / "app/templates/index.html")
        .read_text(encoding="utf-8")
        .replace("{{ASSET_VERSION}}", version)
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(ROOT / "app/static/logo.svg", media_type="image/svg+xml")


@app.get("/api/health")
def health():
    s = Settings.load()
    result = {
        "database_connected": False,
        "gemini_configured": bool(s.api_key),
        "model": s.model,
        "graph": s.graph,
        "error": "",
        "catalog": catalog(),
        "examples": examples(),
    }
    try:
        repo = GraphRepository(s)
        repo.check_connection()
        result["database_connected"] = True
    except DatabaseUnavailable as exc:
        result["error"] = str(exc)
    return result


@app.get("/api/overview")
def overview(service: Service = Depends(get_service)):
    service.repo.initialize()
    return service.assessment()


@app.post("/documents")
def ingest(payload: DocumentInput, service: Service = Depends(get_service)):
    return service.ingest(payload)


@app.get("/facts")
def facts(status: str | None = None, service: Service = Depends(get_service)):
    rows = service.queue()
    return [f for f in rows if not status or f["status"] == status]


@app.post("/facts/{fact_id}/review")
def review(fact_id: str, payload: ReviewInput, service: Service = Depends(get_service)):
    return service.repo.review(fact_id, **payload.model_dump())


@app.post("/assess")
def assessment(payload: AskInput, service: Service = Depends(get_service)):
    return run_agent(service, payload.question, payload.mode, payload.scope)


@app.post("/api/demo")
def demo(payload: DemoInput, service: Service = Depends(get_service)):
    return load_demo(service, payload.mode, payload.include_revision)


@app.get("/api/export")
def export(service: Service = Depends(get_service)):
    snap = service.repo.snapshot()
    return {
        "graph": service.repo.settings.graph,
        "snapshot": snap,
        "history": service.repo.history(),
        "notice": "Contains source text and saved model responses; synthetic demo data only.",
    }


@app.get("/setup")
def setup():
    return FileResponse(ROOT / "docs/setup.md", media_type="text/plain")


# Outermost middleware also protects static files, OpenAPI and error responses.
# Configuration is checked at import so a misconfigured hosted deploy fails closed.
app.add_middleware(DemoSecurityMiddleware, settings=SecuritySettings.load())
