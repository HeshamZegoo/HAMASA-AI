"""Read-only access to public GitHub repository files for HAMASA agents."""
import base64
import re
from typing import Any
from urllib.parse import quote

import httpx

_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_REF_RE = re.compile(r"^[A-Za-z0-9_./-]{1,120}$")
_MAX_FILE_BYTES = 64 * 1024


def validate_github_file_request(owner: str, repo: str, path: str, ref: str = "HEAD") -> tuple[str, str, str, str]:
    """Validate a public repository file target; no arbitrary hosts or private API access."""
    if not isinstance(owner, str) or not _OWNER_RE.fullmatch(owner):
        raise ValueError("Invalid GitHub owner.")
    if not isinstance(repo, str) or not _REPO_RE.fullmatch(repo):
        raise ValueError("Invalid GitHub repository.")
    if not isinstance(path, str) or not path or len(path) > 500:
        raise ValueError("A valid repository file path is required.")
    parts = path.split("/")
    if any(part in {"", ".", ".."} or "\\" in part for part in parts):
        raise ValueError("Invalid repository file path.")
    if not isinstance(ref, str) or not _REF_RE.fullmatch(ref) or ".." in ref:
        raise ValueError("Invalid Git reference.")
    return owner, repo, path, ref


async def read_public_github_file(owner: str, repo: str, path: str, ref: str = "HEAD") -> dict[str, Any]:
    """Read one bounded text file from a public GitHub repository."""
    owner, repo, path, ref = validate_github_file_request(owner, repo, path, ref)
    encoded_path = quote(path, safe="/")
    encoded_ref = quote(ref, safe="")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref={encoded_ref}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "HAMASA-AI-public-repo-reader/1.0",
    }
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=6.0),
        follow_redirects=False,
        trust_env=False,
        headers=headers,
    ) as client:
        response = await client.get(url)
        if response.status_code == 404:
            raise ValueError("The file was not found in that public repository.")
        if response.status_code == 403:
            raise ValueError("GitHub rate limit or access restriction prevented reading this file.")
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or data.get("type") != "file":
        raise ValueError("The requested GitHub path is not a single file.")
    if int(data.get("size") or 0) > _MAX_FILE_BYTES:
        raise ValueError("The GitHub file is larger than the 64 KiB reading limit.")
    if data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
        raise ValueError("GitHub did not return a supported text-file representation.")
    try:
        raw = base64.b64decode(data["content"], validate=False)
        text = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("The GitHub file is not valid UTF-8 text.") from exc
    if len(raw) > _MAX_FILE_BYTES:
        raise ValueError("The GitHub file is larger than the 64 KiB reading limit.")
    return {
        "ok": True,
        "repository": f"{owner}/{repo}",
        "path": path,
        "ref": ref,
        "size": len(raw),
        "content": text,
        "html_url": str(data.get("html_url") or "")[:1000],
    }
