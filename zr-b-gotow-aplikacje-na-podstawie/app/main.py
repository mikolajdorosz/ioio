from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import initialize
from .formats import FORMATS, target_options
from .services import (
    COOKIE_NAME,
    cleanup_expired,
    create_task,
    current_user,
    downloadable_file,
    list_tasks,
    logout,
    request_login_code,
    restore_queued_jobs,
    retry_file,
    task_payload,
    verify_login_code,
)


def configure_logging() -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(settings.log_dir / "application.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(300)
        try:
            cleanup_expired()
        except Exception:
            logging.getLogger("converter").exception("Nie udało się wykonać czyszczenia plików")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    initialize()
    cleanup_expired()
    await restore_queued_jobs()
    task = asyncio.create_task(cleanup_loop(), name="file-cleanup")
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="Konwerter plików multimedialnych",
    version="1.0.0",
    description="Bezpieczny konwerter plików audio, obrazów i wideo.",
    lifespan=lifespan,
)


def get_user(session_token: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> dict:
    return current_user(session_token)


@app.exception_handler(HTTPException)
async def http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception(_: Request, exc: RequestValidationError) -> JSONResponse:
    # The interface is Polish only, so FastAPI's English validation payload is replaced
    # with a single readable message.
    fields = sorted({str(error["loc"][-1]) for error in exc.errors() if error.get("loc")})
    detail = "Żądanie jest niekompletne lub nieprawidłowe."
    if fields:
        detail = f"Żądanie jest niekompletne lub nieprawidłowe (pola: {', '.join(fields)})."
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


@app.post("/api/auth/request-code")
async def auth_request_code(email: str = Form(...)) -> dict:
    return await request_login_code(email)


@app.post("/api/auth/verify")
async def auth_verify(response: Response, email: str = Form(...), code: str = Form(...)) -> dict:
    token, user = verify_login_code(email, code)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"user": user}


@app.post("/api/auth/logout")
async def auth_logout(response: Response, session_token: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> dict:
    logout(session_token)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Wylogowano."}


@app.get("/api/me")
async def me(user: dict = Depends(get_user)) -> dict:
    return {"user": {"email": user["email"], "is_admin": user["is_admin"]}}


@app.get("/api/formats")
async def formats() -> dict:
    return {
        "formats": [
            {
                "code": item.code,
                "label": item.label,
                "category": item.category,
                "profile": item.profile,
                "targets": [{"code": target.code, "label": target.label} for target in target_options(item.code)],
            }
            for item in FORMATS.values()
        ]
    }


@app.get("/api/tasks")
async def tasks(user: dict = Depends(get_user)) -> dict:
    return {"tasks": list_tasks(user["id"])}


@app.get("/api/tasks/{task_id}")
async def task(task_id: str, user: dict = Depends(get_user)) -> dict:
    return task_payload(task_id, user["id"])


@app.post("/api/tasks", status_code=201)
async def new_task(
    files: list[UploadFile] = File(...),
    target_formats: list[str] = Form(...),
    user: dict = Depends(get_user),
) -> dict:
    return await create_task(user["id"], files, target_formats)


@app.post("/api/files/{file_id}/retry")
async def retry(file_id: str, user: dict = Depends(get_user)) -> dict:
    return await retry_file(file_id, user["id"])


@app.get("/api/files/{file_id}/download")
async def download(file_id: str, user: dict = Depends(get_user)) -> FileResponse:
    path, filename = downloadable_file(file_id, user["id"])
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


@app.get("/api/admin/logs")
async def admin_logs(user: dict = Depends(get_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Ta funkcja jest dostępna tylko dla administratora.")
    path = settings.log_dir / "application.log"
    content = path.read_text(encoding="utf-8", errors="replace")[-20_000:] if path.exists() else ""
    return {"logs": content}


STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
