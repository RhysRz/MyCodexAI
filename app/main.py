from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.chat import router as chat_router
from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.workspace import router as workspace_router
from app.api.worktrees import router as worktree_router
from app.api.terminal import router as terminal_router
from app.api.projects import router as project_router
from app.api.sandbox import router as sandbox_router
from app.api.github import router as github_router
from app.api.resilience import router as resilience_router
from app.api.learning import router as learning_router
from app.api.images import router as images_router
from app.api.music import router as music_router
from app.core.settings import settings
from app.core.security import CsrfOriginMiddleware, RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from app.services.auth_service import AuthService
from app.services.cloud_bridge_service import CloudBridgeService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    CloudBridgeService.start()
    try:
        yield
    finally:
        CloudBridgeService.stop()

app = FastAPI(
    title=settings.app_name,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
if settings.force_https:
    app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1_000)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(CsrfOriginMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

app.mount(
    "/static",
    StaticFiles(directory=PROJECT_ROOT / "static"),
    name="static",
)

app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(worktree_router)
app.include_router(terminal_router)
app.include_router(project_router)
app.include_router(sandbox_router)
app.include_router(github_router)
app.include_router(resilience_router)
app.include_router(learning_router)
app.include_router(images_router)
app.include_router(music_router)


@app.get("/", include_in_schema=False)
def agent_workspace(request: Request):
    user = AuthService.user_from_session(request.cookies.get(settings.auth_cookie_name))
    if user is None:
        return FileResponse(PROJECT_ROOT / "templates" / "login.html")
    return FileResponse(PROJECT_ROOT / "templates" / "index.html")


@app.get("/remote", include_in_schema=False)
def remote_workspace(request: Request):
    """A compact authenticated control surface intended for a phone browser."""
    user = AuthService.user_from_session(request.cookies.get(settings.auth_cookie_name))
    if user is None:
        return RedirectResponse("/?next=/remote", status_code=303)
    return FileResponse(PROJECT_ROOT / "templates" / "remote.html")


@app.get("/images", include_in_schema=False)
def image_studio(request: Request):
    """A dedicated private Image Studio, separate from remote computer control."""
    user = AuthService.user_from_session(request.cookies.get(settings.auth_cookie_name))
    if user is None:
        return RedirectResponse("/?next=/images", status_code=303)
    return FileResponse(PROJECT_ROOT / "templates" / "images.html")


@app.get("/music", include_in_schema=False)
def music_lab(request: Request):
    """Private Music Lab for owner-scoped local audio analysis."""
    user = AuthService.user_from_session(request.cookies.get(settings.auth_cookie_name))
    if user is None:
        return RedirectResponse("/?next=/music", status_code=303)
    return FileResponse(PROJECT_ROOT / "templates" / "music.html")


@app.get("/healthz", include_in_schema=False)
def health_check():
    return {"status": "ok"}


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    return FileResponse(PROJECT_ROOT / "static" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(PROJECT_ROOT / "static" / "service-worker.js", media_type="application/javascript")
