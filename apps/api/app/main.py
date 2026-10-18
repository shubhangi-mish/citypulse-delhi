import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import agents, coordination, demo, events, graph, issues, nearby, profiles, system, warnings
from app.core.config import get_settings
from app.db.session import create_tables
from app.graph.client import GraphQueryError, GraphUnavailable, get_graph
from app.graph.schema import ensure_schema
from app.ingestion import sources
from app.security.middleware import CSRFMiddleware, RateLimitMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("citypulse")


def _bootstrap_graph() -> bool:
    try:
        g = get_graph()
        ensure_schema(g)
        sources.ensure_source_nodes(g)
        return True
    except GraphUnavailable:
        log.error("FalkorDB unavailable at startup — graph-powered endpoints will return 503 until it is reachable")
        return False


def _warnings_scheduler(stop: threading.Event) -> None:
    from app.ingestion.run import run

    minutes = get_settings().warnings_refresh_minutes
    while not stop.wait(5 if not hasattr(_warnings_scheduler, "ran") else minutes * 60):
        _warnings_scheduler.ran = True  # type: ignore[attr-defined]
        try:
            log.info("scheduled SACHET refresh: %s", run("src_ndma_sachet"))
        except Exception as exc:
            log.warning("scheduled SACHET refresh failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    _bootstrap_graph()
    stop = threading.Event()
    if get_settings().ingest_schedule:
        threading.Thread(target=_warnings_scheduler, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="CityPulse Delhi API", version="0.1.0", lifespan=lifespan,
              description="Graph-powered civic and community coordination for Delhi, backed by FalkorDB.")
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().web_origin], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(GraphUnavailable)
async def graph_unavailable(_: Request, exc: GraphUnavailable):
    # Explicit failure: no silent fallback to another datastore.
    return JSONResponse(status_code=503, content={
        "error": "graph_unavailable",
        "message": "The CityPulse city graph (FalkorDB) is unavailable, so connected features are paused."})


@app.exception_handler(GraphQueryError)
async def graph_query_error(_: Request, exc: GraphQueryError):
    log.error("graph query error: %s", exc)
    return JSONResponse(status_code=500, content={"error": "graph_query_failed", "message": "Graph query failed."})


@app.exception_handler(PermissionError)
async def permission_error(_: Request, exc: PermissionError):
    return JSONResponse(status_code=403, content={"error": "forbidden", "message": str(exc)})


@app.exception_handler(LookupError)
async def lookup_error(_: Request, exc: LookupError):
    return JSONResponse(status_code=404, content={"error": "not_found", "message": f"{exc} not found"})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"].removeprefix("Value error, ")}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "validation", "message": errors[0]["message"] if errors
                                                  else "Invalid input", "errors": errors})


@app.get("/health")
def health():
    graph_ok = get_graph().ping()
    return JSONResponse(status_code=200 if graph_ok else 503,
                        content={"status": "ok" if graph_ok else "degraded", "falkordb": graph_ok})


for r in (profiles, nearby, issues, events, warnings, graph, coordination, agents, system, demo):
    app.include_router(r.router, prefix="/api/v1")
