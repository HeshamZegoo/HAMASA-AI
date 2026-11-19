import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import main


class AccountAndConversationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "hamasa-test.db"
        self.database_patch = patch.object(main, "DATABASE_URL", f"sqlite:///{database_path}")
        self.jwt_patch = patch.object(main, "JWT_SECRET", "test-secret-" + ("x" * 40))
        self.database_patch.start()
        self.jwt_patch.start()
        main.init_db()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.jwt_patch.stop()
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_signup_creates_account_and_returns_authenticated_session(self):
        response = self.client.post("/api/auth/signup", json={
            "email": "New.User@example.com",
            "password": "correct-horse-battery",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["email"], "new.user@example.com")
        self.assertTrue(data["token"])
        self.assertIn("hamasa_session", response.headers.get("set-cookie", ""))

    def test_signup_rejects_duplicate_email(self):
        payload = {"email": "duplicate@example.com", "password": "correct-horse-battery"}
        self.assertEqual(self.client.post("/api/auth/signup", json=payload).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/signup", json=payload).status_code, 409)

    def test_login_and_cloud_conversation_round_trip(self):
        signup = self.client.post("/api/auth/signup", json={
            "email": "chat@example.com",
            "password": "correct-horse-battery",
        })
        token = signup.json()["token"]
        login = self.client.post("/api/auth/login", json={
            "email": "CHAT@example.com",
            "password": "correct-horse-battery",
        })
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["token"])

        conversation_id = str(uuid.uuid4())
        saved = self.client.put(
            f"/api/chats/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Test conversation",
                "messages": [
                    {"role": "user", "text": "Hello"},
                    {"role": "bot", "text": "Hi"},
                ],
            },
        )
        self.assertEqual(saved.status_code, 200)
        listed = self.client.get("/api/chats", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["conversations"][0]["id"], conversation_id)
        self.assertEqual(listed.json()["conversations"][0]["messages"][1]["text"], "Hi")

    def test_invalid_credentials_are_rejected(self):
        response = self.client.post("/api/auth/login", json={
            "email": "missing@example.com",
            "password": "wrong-password-here",
        })
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
