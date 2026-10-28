from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from .config import settings
from .db import all_rows, connection, iso_after_days, iso_after_minutes, now, one, parse_time, run, transaction
from .formats import FORMATS, allowed_target, conversion_warning
from .media import ConversionError, MediaValidationError, convert_async, result_path, safe_original_name, save_and_detect, source_path
from .security import constant_time_equal, digest, otp, random_token


logger = logging.getLogger("converter")
COOKIE_NAME = "konwerter_session"
_queue_limit = asyncio.Semaphore(settings.max_conversions)
_queued_file_ids: set[str] = set()
_queue_guard = asyncio.Lock()


def _as_dict(row) -> dict:
    return dict(row) if row else {}


def _email_ok(email: str) -> bool:
    import re

    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)) and len(email) <= 254


def _send_email(address: str, code: str) -> None:
    if not settings.smtp_host:
        logger.warning("SMTP nie jest skonfigurowany; kod wysłany tylko do dziennika dla %s", address)
        return
    message = EmailMessage()
    message["Subject"] = "Kod logowania do Konwertera plików"
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = address
    message.set_content(
        f"Twój jednorazowy kod logowania: {code}\n\nKod jest ważny przez {settings.otp_minutes} minut i można go użyć tylko raz."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


async def request_login_code(email: str) -> dict:
    email = email.strip().lower()
    if not _email_ok(email):
        raise HTTPException(status_code=422, detail="Podaj prawidłowy adres e-mail.")
    value = otp()
    timestamp = now()
    with transaction() as conn:
        conn.execute("UPDATE one_time_codes SET used = 1 WHERE email = ? AND used = 0", (email,))
        conn.execute(
            "INSERT INTO one_time_codes (id, user_id, email, code_hash, expires_at, attempts, used, created_at) VALUES (?, NULL, ?, ?, ?, 0, 0, ?)",
            (str(uuid.uuid4()), email, digest(value), iso_after_minutes(settings.otp_minutes), timestamp),
        )
    try:
        await asyncio.to_thread(_send_email, email, value)
    except Exception:
        logger.exception("Nie udało się wysłać wiadomości z kodem do %s", email)
        raise HTTPException(status_code=503, detail="Nie udało się wysłać kodu. Spróbuj ponownie później.")
    logger.info("Wysłano kod jednorazowy do %s", email)
    response = {"message": "Kod jednorazowy został wysłany na podany adres e-mail."}
    if settings.is_development and not settings.smtp_host:
        response["development_code"] = value
    return response


def _active_user_count(conn) -> int:
    threshold = iso_after_minutes(-settings.active_window_minutes)
    return int(
        conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM sessions WHERE revoked_at IS NULL AND expires_at > ? AND last_active_at > ?",
            (now(), threshold),
        ).fetchone()[0]
    )


def verify_login_code(email: str, code: str) -> tuple[str, dict]:
    email = email.strip().lower()
    if not _email_ok(email) or not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=422, detail="Podaj e-mail i sześciocyfrowy kod.")
    with transaction() as conn:
        record = conn.execute(
            "SELECT * FROM one_time_codes WHERE email = ? ORDER BY created_at DESC LIMIT 1", (email,)
        ).fetchone()
        if record is None or record["used"] or parse_time(record["expires_at"]) <= datetime.now(UTC):
            raise HTTPException(status_code=401, detail="Kod jest nieważny lub wygasł. Zamów nowy kod.")
        if record["attempts"] >= settings.otp_max_attempts:
            conn.execute("UPDATE one_time_codes SET used = 1 WHERE id = ?", (record["id"],))
            raise HTTPException(status_code=401, detail="Wykorzystano limit prób. Zamów nowy kod.")
        if not constant_time_equal(record["code_hash"], digest(code)):
            attempts = record["attempts"] + 1
            conn.execute("UPDATE one_time_codes SET attempts = ?, used = ? WHERE id = ?", (attempts, int(attempts >= settings.otp_max_attempts), record["id"]))
            left = max(0, settings.otp_max_attempts - attempts)
            raise HTTPException(status_code=401, detail=f"Nieprawidłowy kod. Pozostało prób: {left}.")

        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None:
            user_id = str(uuid.uuid4())
            conn.execute("INSERT INTO users (id, email, created_at) VALUES (?, ?, ?)", (user_id, email, now()))
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if _active_user_count(conn) >= settings.max_active_users:
            already_active = conn.execute(
                "SELECT 1 FROM sessions WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ? AND last_active_at > ? LIMIT 1",
                (user["id"], now(), iso_after_minutes(-settings.active_window_minutes)),
            ).fetchone()
            if not already_active:
                raise HTTPException(status_code=503, detail="Serwer jest obecnie zajęty. Spróbuj ponownie za kilka minut.")

        raw_token = random_token()
        conn.execute("UPDATE one_time_codes SET used = 1, user_id = ? WHERE id = ?", (user["id"], record["id"]))
        conn.execute(
            "INSERT INTO sessions (id, user_id, token_hash, expires_at, last_active_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user["id"], digest(raw_token), iso_after_days(settings.session_days), now(), now()),
        )
    logger.info("Utworzono sesję dla %s", email)
    return raw_token, {"email": user["email"], "is_admin": user["email"].lower() in settings.admin_emails}


def current_user(token: str | None) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Zaloguj się, aby kontynuować.")
    with transaction() as conn:
        session = conn.execute(
            "SELECT sessions.*, users.email FROM sessions JOIN users ON users.id = sessions.user_id WHERE token_hash = ? AND revoked_at IS NULL",
            (digest(token),),
        ).fetchone()
        if session is None or parse_time(session["expires_at"]) <= datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesja wygasła. Zaloguj się ponownie.")
        conn.execute("UPDATE sessions SET last_active_at = ? WHERE id = ?", (now(), session["id"]))
    return {"id": session["user_id"], "email": session["email"], "is_admin": session["email"].lower() in settings.admin_emails}


def logout(token: str | None) -> None:
    if token:
        run("UPDATE sessions SET revoked_at = ? WHERE token_hash = ?", (now(), digest(token)))


async def create_task(user_id: str, uploads: list[UploadFile], target_formats: list[str]) -> dict:
    if not uploads:
        raise HTTPException(status_code=422, detail="Dodaj co najmniej jeden plik.")
    if len(uploads) > settings.max_files_per_task:
        raise HTTPException(status_code=422, detail="Jedno zadanie może zawierać najwyżej dwa pliki.")
    if len(target_formats) != len(uploads):
        raise HTTPException(status_code=422, detail="Wybierz format docelowy dla każdego pliku.")

    prepared: list[dict] = []
    try:
        for upload, target in zip(uploads, target_formats, strict=True):
            file_id = str(uuid.uuid4())
            temporary = settings.storage_dir / f"{file_id}.upload"
            size_bytes, source_format = await save_and_detect(upload, temporary, settings.max_file_bytes)
            target = target.lower().strip()
            if not allowed_target(source_format, target):
                temporary.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=422,
                    detail=f"Dla pliku {safe_original_name(upload.filename)} wybierz jeden z dwóch formatów z tej samej kategorii.",
                )
            prepared.append({
                "id": file_id,
                "temporary": temporary,
                "original_name": safe_original_name(upload.filename),
                "source_format": source_format,
                "target_format": target,
                "size_bytes": size_bytes,
            })
        task_id = str(uuid.uuid4())
        with transaction() as conn:
            conn.execute("INSERT INTO conversion_tasks (id, user_id, status, created_at) VALUES (?, ?, 'oczekuje', ?)", (task_id, user_id, now()))
            for item in prepared:
                item["temporary"].replace(source_path(item["id"], item["source_format"]))
                conn.execute(
                    "INSERT INTO files (id, task_id, original_name, source_format, target_format, size_bytes, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'oczekuje', ?)",
                    (item["id"], task_id, item["original_name"], item["source_format"], item["target_format"], item["size_bytes"], now()),
                )
    except (MediaValidationError, HTTPException) as exc:
        for item in prepared:
            item["temporary"].unlink(missing_ok=True)
            source_path(item["id"], item["source_format"]).unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        for item in prepared:
            item["temporary"].unlink(missing_ok=True)
            source_path(item["id"], item["source_format"]).unlink(missing_ok=True)
        logger.exception("Błąd podczas zapisu plików")
        raise HTTPException(status_code=500, detail="Nie udało się zapisać plików.")

    for item in prepared:
        await enqueue(item["id"])
    logger.info("Utworzono zadanie %s z %s plikami", task_id, len(prepared))
    return task_payload(task_id, user_id)


def _refresh_task_status(task_id: str) -> None:
    rows = all_rows("SELECT status FROM files WHERE task_id = ?", (task_id,))
    states = {row["status"] for row in rows}
    if "w toku" in states:
        task_status = "w toku"
    elif "oczekuje" in states:
        task_status = "oczekuje"
    elif states == {"błąd"}:
        task_status = "błąd"
    else:
        task_status = "gotowe"
    run("UPDATE conversion_tasks SET status = ? WHERE id = ?", (task_status, task_id))


async def enqueue(file_id: str) -> None:
    async with _queue_guard:
        if file_id in _queued_file_ids:
            return
        _queued_file_ids.add(file_id)
    asyncio.create_task(_process_file(file_id), name=f"conversion-{file_id}")


async def _process_file(file_id: str) -> None:
    try:
        async with _queue_limit:
            file = one("SELECT * FROM files WHERE id = ?", (file_id,))
            if file is None or file["status"] != "oczekuje":
                return
            run("UPDATE files SET status = 'w toku', started_at = ?, error_code = NULL WHERE id = ?", (now(), file_id))
            _refresh_task_status(file["task_id"])
            try:
                await convert_async(
                    source_path(file["id"], file["source_format"]),
                    result_path(file["id"], file["target_format"]),
                    file["source_format"],
                    file["target_format"],
                )
                run(
                    "UPDATE files SET status = 'gotowe', completed_at = ?, delete_at = ? WHERE id = ?",
                    (now(), iso_after_minutes(settings.retention_minutes), file_id),
                )
                logger.info("Zakończono konwersję pliku %s", file_id)
            except (ConversionError, Exception) as exc:
                logger.exception("Konwersja pliku %s nie powiodła się", file_id)
                run(
                    "UPDATE files SET status = 'błąd', error_code = ?, completed_at = ?, delete_at = ? WHERE id = ?",
                    (str(exc)[:500], now(), iso_after_minutes(settings.retention_minutes), file_id),
                )
            _refresh_task_status(file["task_id"])
    finally:
        async with _queue_guard:
            _queued_file_ids.discard(file_id)


def _file_payload(row) -> dict:
    warning = conversion_warning(row["source_format"], row["target_format"])
    return {
        "id": row["id"],
        "original_name": row["original_name"],
        "source_format": row["source_format"],
        "target_format": row["target_format"],
        "size_bytes": row["size_bytes"],
        "status": row["status"],
        "error": row["error_code"],
        "delete_at": row["delete_at"],
        "warning": warning,
        "can_download": row["status"] == "gotowe" and result_path(row["id"], row["target_format"]).exists(),
        "can_retry": row["status"] == "błąd",
    }


def task_payload(task_id: str, user_id: str) -> dict:
    task = one("SELECT * FROM conversion_tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono zadania.")
    files = all_rows("SELECT * FROM files WHERE task_id = ? ORDER BY created_at", (task_id,))
    return {"id": task["id"], "status": task["status"], "created_at": task["created_at"], "files": [_file_payload(item) for item in files]}


def list_tasks(user_id: str) -> list[dict]:
    return [task_payload(row["id"], user_id) for row in all_rows("SELECT id FROM conversion_tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT 30", (user_id,))]


async def retry_file(file_id: str, user_id: str) -> dict:
    row = one(
        "SELECT files.* FROM files JOIN conversion_tasks ON conversion_tasks.id = files.task_id WHERE files.id = ? AND conversion_tasks.user_id = ?",
        (file_id, user_id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono pliku.")
    if row["status"] != "błąd":
        raise HTTPException(status_code=409, detail="Ponowić można tylko konwersję zakończoną błędem.")
    if not source_path(row["id"], row["source_format"]).exists():
        raise HTTPException(status_code=410, detail="Plik źródłowy został już usunięty.")
    run("UPDATE files SET status = 'oczekuje', error_code = NULL, completed_at = NULL, delete_at = NULL WHERE id = ?", (file_id,))
    _refresh_task_status(row["task_id"])
    await enqueue(file_id)
    return task_payload(row["task_id"], user_id)


def downloadable_file(file_id: str, user_id: str) -> tuple[Path, str]:
    row = one(
        "SELECT files.* FROM files JOIN conversion_tasks ON conversion_tasks.id = files.task_id WHERE files.id = ? AND conversion_tasks.user_id = ?",
        (file_id, user_id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono pliku.")
    path = result_path(row["id"], row["target_format"])
    if row["status"] != "gotowe" or not path.exists():
        raise HTTPException(status_code=409, detail="Wynik nie jest jeszcze dostępny.")
    original_stem = Path(row["original_name"]).stem or "wynik"
    return path, f"{safe_original_name(original_stem)}.{row['target_format']}"


def cleanup_expired() -> int:
    expired = all_rows("SELECT * FROM files WHERE delete_at IS NOT NULL AND delete_at <= ?", (now(),))
    if not expired:
        return 0
    with transaction() as conn:
        for item in expired:
            source_path(item["id"], item["source_format"]).unlink(missing_ok=True)
            result_path(item["id"], item["target_format"]).unlink(missing_ok=True)
            conn.execute("DELETE FROM files WHERE id = ?", (item["id"],))
        conn.execute("DELETE FROM conversion_tasks WHERE id NOT IN (SELECT DISTINCT task_id FROM files)")
    logger.info("Usunięto %s wygasłych plików", len(expired))
    return len(expired)


async def restore_queued_jobs() -> None:
    # A worker interrupted by a restart may have left a file in progress. Its source
    # remains on disk, therefore safely return it to the durable queue.
    run("UPDATE files SET status = 'oczekuje', error_code = NULL WHERE status = 'w toku'")
    for row in all_rows("SELECT id FROM files WHERE status = 'oczekuje'"):
        await enqueue(row["id"])
