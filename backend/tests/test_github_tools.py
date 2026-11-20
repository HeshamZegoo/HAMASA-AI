import unittest

from backend.app.github_tools import validate_github_file_request


class PublicGitHubReaderValidationTests(unittest.TestCase):
    def test_accepts_public_repo_file(self):
        self.assertEqual(
            validate_github_file_request("octocat", "hello-world", "README.md", "main"),
            ("octocat", "hello-world", "README.md", "main"),
        )

    def test_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("octocat", "hello-world", "../secrets.txt")

    def test_rejects_backslash_path(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("octocat", "hello-world", "src\\..\\secret")

    def test_rejects_invalid_ref(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("octocat", "hello-world", "README.md", "../../main")

    def test_rejects_url_as_owner(self):
        with self.assertRaises(ValueError):
            validate_github_file_request("https://evil.example", "repo", "README.md")


if __name__ == "__main__":
    unittest.main()
