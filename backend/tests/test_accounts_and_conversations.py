import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
import sqlite3

from backend.app import main


class AccountAndConversationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "hamasa-test.db"
        self.database_patch = patch.object(main, "DATABASE_URL", f"sqlite:///{database_path}")
        self.jwt_patch = patch.object(main, "JWT_SECRET", "test-secret-" + ("x" * 40))
        self.memory_key = Fernet.generate_key().decode("ascii")
        self.memory_patch = patch.object(main, "MEMORY_ENCRYPTION_KEY", self.memory_key)
        self.database_patch.start()
        self.jwt_patch.start()
        self.memory_patch.start()
        main.init_db()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.memory_patch.stop()
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

    def test_saved_memory_is_encrypted_at_rest_and_decrypted_for_owner(self):
        signup = self.client.post("/api/auth/signup", json={
            "email": "memory@example.com",
            "password": "correct-horse-battery",
        })
        token = signup.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        created = self.client.post("/api/memory", headers=headers, json={
            "category": "preference",
            "text": "أفضل الرد بالمصري",
        })
        self.assertEqual(created.status_code, 200)
        memory_id = created.json()["id"]

        database_path = Path(self.temp_dir.name) / "hamasa-test.db"
        with sqlite3.connect(database_path) as db:
            stored = db.execute(
                "SELECT content FROM hamasa_memories WHERE id = ?", (memory_id,)
            ).fetchone()[0]
        self.assertTrue(stored.startswith("enc:v1:"))
        self.assertNotIn("أفضل الرد بالمصري", stored)

        listed = self.client.get("/api/memory", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["memories"][0]["text"], "أفضل الرد بالمصري")

    def test_users_cannot_read_or_overwrite_another_users_conversation(self):
        first = self.client.post("/api/auth/signup", json={
            "email": "owner@example.com",
            "password": "correct-horse-battery",
        }).json()["token"]
        second = self.client.post("/api/auth/signup", json={
            "email": "outsider@example.com",
            "password": "correct-horse-battery",
        }).json()["token"]
        conversation_id = str(uuid.uuid4())
        owner_headers = {"Authorization": f"Bearer {first}"}
        outsider_headers = {"Authorization": f"Bearer {second}"}
        created = self.client.put(
            f"/api/chats/{conversation_id}",
            headers=owner_headers,
            json={"title": "Private", "messages": [{"role": "user", "text": "secret"}]},
        )
        self.assertEqual(created.status_code, 200)
        outsider_list = self.client.get("/api/chats", headers=outsider_headers)
        self.assertEqual(outsider_list.json()["conversations"], [])
        overwrite = self.client.put(
            f"/api/chats/{conversation_id}",
            headers=outsider_headers,
            json={"title": "Stolen", "messages": [{"role": "user", "text": "changed"}]},
        )
        self.assertEqual(overwrite.status_code, 404)
        owner_list = self.client.get("/api/chats", headers=owner_headers)
        self.assertEqual(owner_list.json()["conversations"][0]["title"], "Private")

    def test_logout_revokes_the_session_token(self):
        signup = self.client.post("/api/auth/signup", json={
            "email": "logout@example.com",
            "password": "correct-horse-battery",
        })
        token = signup.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        logged_out = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logged_out.status_code, 200)
        self.assertEqual(logged_out.json(), {"logged_out": True})
        denied = self.client.get("/api/chats", headers=headers)
        self.assertEqual(denied.status_code, 401)

    def test_invalid_credentials_are_rejected(self):
        response = self.client.post("/api/auth/login", json={
            "email": "missing@example.com",
            "password": "wrong-password-here",
        })
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
