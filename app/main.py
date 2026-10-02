import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.catalog import CatalogError, fetch_catalog
from app.config import Settings
from app.models import CatalogResponse

STATIC = Path(__file__).parent / "static"
CSP = (
    "default-src 'self'; script-src 'self' https://www.youtube.com https://s.ytimg.com; "
    "style-src 'self'; img-src 'self' https://i.ytimg.com data:; "
    "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
    "connect-src 'self' https://www.youtube.com; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'self'; form-action 'self'"
)


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings.from_env()
        logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        # Upstream libraries must never log authentication headers or response bodies.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        app.state.settings = config
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            app.state.http = client
            yield

    app = FastAPI(title="NextSet", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = CSP
        if request.url.path == "/api/catalog":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(CatalogError)
    async def catalog_error(request, error: CatalogError):
        headers = {"Cache-Control": "no-store"}
        if error.retry_after is not None:
            headers["Retry-After"] = str(error.retry_after)
        return JSONResponse({"error": {"code": error.code, "message": error.message}}, status_code=error.status, headers=headers)

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        # Do not serialize exceptions: upstream errors can contain sensitive data.
        logging.getLogger("nextset").error("unexpected_error type=%s", type(error).__name__)
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "Si è verificato un errore. Riprova più tardi."}},
                            status_code=500, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin", "Content-Security-Policy": CSP})

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/api/catalog", response_model=CatalogResponse)
    async def catalog(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await fetch_catalog(request.app.state.http, request.app.state.settings)
        except CatalogError:
            raise
        except Exception as error:
            logging.getLogger("nextset").error("catalog_unexpected_error type=%s", type(error).__name__)
            raise CatalogError("INTERNAL_ERROR") from None

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
