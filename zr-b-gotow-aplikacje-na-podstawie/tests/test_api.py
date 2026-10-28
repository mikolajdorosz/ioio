"""Testy API całego przepływu: logowanie kodem, zadania, limity, uprawnienia i czyszczenie.

Konfiguracja środowiska musi zostać ustawiona przed importem aplikacji, ponieważ
``app.config.settings`` jest tworzone podczas importu.
"""

import io
import os
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="konwerter-testy-"))
os.environ.update(
    {
        "APP_ENV": "development",
        "SMTP_HOST": "",
        "SECRET_KEY": "sekret-testowy",
        "DATABASE_PATH": str(TEST_ROOT / "test.db"),
        "STORAGE_DIR": str(TEST_ROOT / "storage"),
        "LOG_DIR": str(TEST_ROOT / "logs"),
        "MAX_ACTIVE_USERS": "2",
        "MAX_FILE_BYTES": str(1024 * 1024),
        "OTP_REQUESTS_PER_WINDOW": "5",
        "ADMIN_EMAILS": "admin@example.pl",
    }
)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import connection  # noqa: E402
from app.main import app  # noqa: E402
from app.services import COOKIE_NAME, cleanup_expired  # noqa: E402

FINAL_STATES = {"gotowe", "błąd"}


def png_bytes(size=(9, 7), mode="RGBA") -> bytes:
    image = Image.new(mode, size, (200, 30, 30, 0) if mode == "RGBA" else (200, 30, 30))
    if mode == "RGBA":
        image.putpixel((0, 0), (10, 200, 10, 255))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def jpg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 0, 255)).save(buffer, "JPEG")
    return buffer.getvalue()


def fake_wav_bytes() -> bytes:
    # Nagłówek RIFF/WAVE bez poprawnych danych: sygnatura jest rozpoznawana, a konwersja
    # musi zakończyć się statusem "błąd" niezależnie od obecności FFmpeg.
    return b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"\x00" * 64


class ApiTestCase(unittest.TestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def setUp(self):
        # Każdy test startuje z pustą bazą, aby limity użytkowników się nie nakładały.
        with connection() as conn:
            conn.execute("DELETE FROM files")
            conn.execute("DELETE FROM conversion_tasks")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM one_time_codes")
            conn.execute("DELETE FROM users")
        for path in settings.storage_dir.iterdir():
            if path.is_file() and path.name != ".gitkeep":
                path.unlink()
        self.client.cookies.clear()

    # --- pomocnicze -----------------------------------------------------------------
    def request_code(self, email: str):
        return self.client.post("/api/auth/request-code", data={"email": email})

    def verify(self, email: str, code: str):
        response = self.client.post("/api/auth/verify", data={"email": email, "code": code})
        self.client.cookies.clear()
        return response

    def login(self, email: str) -> dict:
        response = self.request_code(email)
        self.assertEqual(response.status_code, 200, response.text)
        code = response.json()["development_code"]
        response = self.verify(email, code)
        self.assertEqual(response.status_code, 200, response.text)
        token = response.cookies.get(COOKIE_NAME)
        self.assertTrue(token)
        return {"Cookie": f"{COOKIE_NAME}={token}"}

    def wait_for_task(self, task_id: str, headers: dict, timeout: float = 60.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            payload = self.client.get(f"/api/tasks/{task_id}", headers=headers).json()
            if all(item["status"] in FINAL_STATES for item in payload["files"]):
                return payload
            time.sleep(0.2)
        self.fail(f"Zadanie {task_id} nie zakończyło się w czasie {timeout} s")

    def create_task(self, headers: dict, files: list[tuple[str, bytes]], targets: list[str]):
        multipart = [("files", (name, content, "application/octet-stream")) for name, content in files]
        return self.client.post("/api/tasks", headers=headers, files=multipart, data={"target_formats": targets})

    def set_last_active(self, email: str, minutes_ago: int) -> None:
        stamp = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()
        with connection() as conn:
            conn.execute(
                "UPDATE sessions SET last_active_at = ? WHERE user_id = (SELECT id FROM users WHERE email = ?)",
                (stamp, email),
            )


class AuthTests(ApiTestCase):
    def test_health_and_static_index(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Konwerter plików multimedialnych", page.text)
        self.assertEqual(self.client.get("/styles.css").status_code, 200)
        self.assertEqual(self.client.get("/app.js").status_code, 200)

    def test_requires_login_with_polish_message(self):
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Zaloguj się, aby kontynuować.")

    def test_rejects_invalid_email(self):
        response = self.request_code("to-nie-jest-email")
        self.assertEqual(response.status_code, 422)
        self.assertIn("prawidłowy adres", response.json()["detail"])

    def test_validation_errors_are_polish(self):
        response = self.client.post("/api/auth/request-code", data={})
        self.assertEqual(response.status_code, 422)
        self.assertIn("niekompletne", response.json()["detail"])
        self.assertIn("email", response.json()["detail"])

    def test_full_login_creates_account_cookie_and_logout_revokes(self):
        email = "anna@example.pl"
        response = self.request_code(email)
        self.assertEqual(response.status_code, 200)
        code = response.json()["development_code"]
        self.assertRegex(code, r"^\d{6}$")

        with connection() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone())
            stored = conn.execute("SELECT code_hash FROM one_time_codes WHERE email = ?", (email,)).fetchone()[0]
        self.assertNotEqual(stored, code, "kod nie może być zapisany jawnie")

        response = self.verify(email, code)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"], {"email": email, "is_admin": False})
        set_cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", set_cookie)
        self.assertIn("samesite=lax", set_cookie)
        self.assertIn(f"max-age={settings.session_days * 86400}", set_cookie)
        headers = {"Cookie": f"{COOKIE_NAME}={response.cookies[COOKIE_NAME]}"}

        with connection() as conn:
            self.assertIsNotNone(conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone())

        self.assertEqual(self.client.get("/api/me", headers=headers).json()["user"]["email"], email)

        # kod jest jednorazowy
        self.assertEqual(self.verify(email, code).status_code, 401)

        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=headers).status_code, 401)

    def test_wrong_code_five_times_invalidates_code(self):
        email = "blad@example.pl"
        code = self.request_code(email).json()["development_code"]
        wrong = "000000" if code != "000000" else "111111"
        for attempt in range(1, 6):
            response = self.verify(email, wrong)
            self.assertEqual(response.status_code, 401)
            self.assertIn(f"Pozostało prób: {5 - attempt}", response.json()["detail"])
        response = self.verify(email, code)
        self.assertEqual(response.status_code, 401, "po 5 próbach nawet poprawny kod ma być odrzucony")
        self.assertIn("Zamów nowy kod", response.json()["detail"])
        with connection() as conn:
            row = conn.execute("SELECT attempts, used FROM one_time_codes WHERE email = ?", (email,)).fetchone()
        self.assertEqual((row["attempts"], row["used"]), (5, 1), "licznik prób musi być trwale zapisany")

    def test_expired_code_is_rejected(self):
        email = "wygasly@example.pl"
        code = self.request_code(email).json()["development_code"]
        with connection() as conn:
            conn.execute(
                "UPDATE one_time_codes SET expires_at = ? WHERE email = ?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), email),
            )
        response = self.verify(email, code)
        self.assertEqual(response.status_code, 401)
        self.assertIn("wygasł", response.json()["detail"])

    def test_requesting_new_code_invalidates_previous(self):
        email = "nowy@example.pl"
        first = self.request_code(email).json()["development_code"]
        second = self.request_code(email).json()["development_code"]
        self.assertEqual(self.verify(email, first).status_code, 401)
        self.assertEqual(self.verify(email, second).status_code, 200)

    def test_code_requests_are_rate_limited(self):
        email = "spam@example.pl"
        for _ in range(settings.otp_requests_per_window):
            self.assertEqual(self.request_code(email).status_code, 200)
        response = self.request_code(email)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Zbyt wiele", response.json()["detail"])

    def test_admin_flag_and_logs_endpoint(self):
        user = self.login("zwykly@example.pl")
        self.assertEqual(self.client.get("/api/admin/logs", headers=user).status_code, 403)
        self.set_last_active("zwykly@example.pl", 30)
        admin = self.login("admin@example.pl")
        self.assertTrue(self.client.get("/api/me", headers=admin).json()["user"]["is_admin"])
        response = self.client.get("/api/admin/logs", headers=admin)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Utworzono sesję", response.json()["logs"])


class CapacityTests(ApiTestCase):
    def test_busy_server_blocks_eleventh_user_at_login(self):
        first = self.login("u1@example.pl")
        self.login("u2@example.pl")
        code = self.request_code("u3@example.pl").json()["development_code"]
        response = self.verify("u3@example.pl", code)
        self.assertEqual(response.status_code, 503)
        self.assertIn("zajęty", response.json()["detail"])
        # Aktywny użytkownik może zalogować się ponownie mimo pełnego limitu.
        code = self.request_code("u1@example.pl").json()["development_code"]
        self.assertEqual(self.verify("u1@example.pl", code).status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=first).status_code, 200)

    def test_inactive_users_free_capacity_and_returning_session_sees_busy(self):
        first = self.login("u1@example.pl")
        self.login("u2@example.pl")
        self.set_last_active("u1@example.pl", settings.active_window_minutes + 1)
        third = self.login("u3@example.pl")
        self.assertEqual(self.client.get("/api/me", headers=third).status_code, 200)
        # Zapamiętana sesja u1 wraca, gdy limit jest wyczerpany przez u2 i u3.
        response = self.client.get("/api/me", headers=first)
        self.assertEqual(response.status_code, 503)
        self.assertIn("zajęty", response.json()["detail"])
        with connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions WHERE revoked_at IS NULL").fetchone()[0], 3)


class TaskTests(ApiTestCase):
    def test_png_to_jpg_flattens_transparency_and_is_downloadable(self):
        headers = self.login("obraz@example.pl")
        response = self.create_task(headers, [("zdjęcie: test.png", png_bytes())], ["jpg"])
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "oczekuje")
        file = payload["files"][0]
        self.assertEqual(file["source_format"], "png")
        self.assertEqual(file["target_format"], "jpg")
        self.assertEqual(file["original_name"], "zdjęcie_ test.png")
        self.assertEqual(file["size_bytes"], len(png_bytes()))
        self.assertIn("stratnym", file["warning"])

        payload = self.wait_for_task(payload["id"], headers)
        file = payload["files"][0]
        self.assertEqual(file["status"], "gotowe", file["error"])
        self.assertEqual(payload["status"], "gotowe")
        self.assertTrue(file["can_download"])
        self.assertFalse(file["can_retry"])
        self.assertIsNotNone(file["delete_at"])

        download = self.client.get(f"/api/files/{file['id']}/download", headers=headers)
        self.assertEqual(download.status_code, 200)
        self.assertIn("test.jpg", download.headers["content-disposition"])
        with Image.open(io.BytesIO(download.content)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (9, 7))
            # JPEG może wprowadzić odchylenie o 1-2 poziomy, więc sprawdzamy "praktycznie biały".
            self.assertTrue(all(channel >= 250 for channel in image.getpixel((5, 5))), "przezroczystość ma być białym tłem")

        with connection() as conn:
            row = conn.execute("SELECT id FROM files WHERE id = ?", (file["id"],)).fetchone()
        self.assertTrue((settings.storage_dir / f"{row['id']}.png").exists())
        self.assertTrue((settings.storage_dir / f"{row['id']}.wynik.jpg").exists())

    def test_jpg_to_png_and_png_to_heic(self):
        headers = self.login("obrazy@example.pl")
        response = self.create_task(headers, [("a.jpg", jpg_bytes()), ("b.png", png_bytes())], ["png", "heic"])
        self.assertEqual(response.status_code, 201, response.text)
        payload = self.wait_for_task(response.json()["id"], headers)
        statuses = {item["target_format"]: item for item in payload["files"]}
        self.assertEqual(statuses["png"]["status"], "gotowe", statuses["png"]["error"])
        self.assertEqual(statuses["heic"]["status"], "gotowe", statuses["heic"]["error"])
        heic = self.client.get(f"/api/files/{statuses['heic']['id']}/download", headers=headers).content
        self.assertIn(b"ftyp", heic[:12])
        png = self.client.get(f"/api/files/{statuses['png']['id']}/download", headers=headers).content
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_corrupt_file_fails_independently_and_can_be_retried(self):
        headers = self.login("mieszane@example.pl")
        response = self.create_task(headers, [("ok.png", png_bytes()), ("zepsuty.wav", fake_wav_bytes())], ["jpg", "mp3"])
        self.assertEqual(response.status_code, 201, response.text)
        payload = self.wait_for_task(response.json()["id"], headers)
        by_target = {item["target_format"]: item for item in payload["files"]}
        self.assertEqual(by_target["jpg"]["status"], "gotowe", by_target["jpg"]["error"])
        self.assertEqual(by_target["mp3"]["status"], "błąd")
        self.assertTrue(by_target["mp3"]["can_retry"])
        self.assertTrue(by_target["mp3"]["error"])
        self.assertEqual(payload["status"], "gotowe", "błąd jednego pliku nie blokuje zadania")

        self.assertEqual(self.client.post(f"/api/files/{by_target['jpg']['id']}/retry", headers=headers).status_code, 409)
        retry = self.client.post(f"/api/files/{by_target['mp3']['id']}/retry", headers=headers)
        self.assertEqual(retry.status_code, 200, retry.text)
        payload = self.wait_for_task(payload["id"], headers)
        again = next(item for item in payload["files"] if item["target_format"] == "mp3")
        self.assertEqual(again["status"], "błąd")
        self.assertTrue(again["can_retry"])

    def test_rejects_third_file_wrong_target_unknown_format_and_oversize(self):
        headers = self.login("walidacja@example.pl")
        png = png_bytes()

        response = self.create_task(headers, [("1.png", png), ("2.png", png), ("3.png", png)], ["jpg", "jpg", "jpg"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("najwyżej dwa pliki", response.json()["detail"])

        response = self.create_task(headers, [("1.png", png)], ["mp3"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("tej samej kategorii", response.json()["detail"])

        response = self.create_task(headers, [("1.png", png)], ["png"])
        self.assertEqual(response.status_code, 422)

        response = self.create_task(headers, [("dokument.pdf", b"%PDF-1.7 nie jest multimediami")], ["jpg"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("Nie rozpoznano", response.json()["detail"])

        response = self.create_task(headers, [("udaje.png", b"%PDF-1.7 zla zawartosc")], ["jpg"])
        self.assertEqual(response.status_code, 422, "format liczy się po zawartości, nie po rozszerzeniu")

        response = self.create_task(headers, [("duzy.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * settings.max_file_bytes)], ["jpg"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("przekracza limit", response.json()["detail"])

        response = self.create_task(headers, [("1.png", png), ("2.png", png)], ["jpg"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("dla każdego pliku", response.json()["detail"])

        self.assertEqual(self.client.get("/api/tasks", headers=headers).json()["tasks"], [])
        leftovers = [path for path in settings.storage_dir.iterdir() if path.name != ".gitkeep"]
        self.assertEqual(leftovers, [], "odrzucone pliki nie mogą zostać na dysku")

    def test_users_cannot_access_each_others_files(self):
        owner = self.login("wlasciciel@example.pl")
        response = self.create_task(owner, [("a.png", png_bytes())], ["jpg"])
        payload = self.wait_for_task(response.json()["id"], owner)
        file_id = payload["files"][0]["id"]

        self.set_last_active("wlasciciel@example.pl", settings.active_window_minutes + 1)
        intruder = self.login("obcy@example.pl")
        self.assertEqual(self.client.get(f"/api/tasks/{payload['id']}", headers=intruder).status_code, 404)
        self.assertEqual(self.client.get(f"/api/files/{file_id}/download", headers=intruder).status_code, 404)
        self.assertEqual(self.client.post(f"/api/files/{file_id}/retry", headers=intruder).status_code, 404)
        self.assertEqual(self.client.get("/api/tasks", headers=intruder).json()["tasks"], [])

    def test_cleanup_removes_expired_results_and_tasks(self):
        headers = self.login("czyszczenie@example.pl")
        response = self.create_task(headers, [("a.png", png_bytes())], ["jpg"])
        payload = self.wait_for_task(response.json()["id"], headers)
        file = payload["files"][0]
        delete_at = datetime.fromisoformat(file["delete_at"])
        created = datetime.fromisoformat(payload["created_at"])
        self.assertAlmostEqual((delete_at - created).total_seconds(), settings.retention_minutes * 60, delta=120)

        self.assertEqual(cleanup_expired(), 0, "plik przed terminem nie może zostać usunięty")
        with connection() as conn:
            conn.execute("UPDATE files SET delete_at = ? WHERE id = ?", ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), file["id"]))
        self.assertEqual(cleanup_expired(), 1)
        self.assertFalse((settings.storage_dir / f"{file['id']}.png").exists())
        self.assertFalse((settings.storage_dir / f"{file['id']}.wynik.jpg").exists())
        self.assertEqual(self.client.get("/api/tasks", headers=headers).json()["tasks"], [])
        self.assertEqual(self.client.get(f"/api/files/{file['id']}/download", headers=headers).status_code, 404)

    def test_formats_endpoint_lists_eighteen_paths(self):
        payload = self.client.get("/api/formats").json()["formats"]
        self.assertEqual(len(payload), 9)
        self.assertEqual(sum(len(item["targets"]) for item in payload), 18)


if __name__ == "__main__":
    unittest.main()
