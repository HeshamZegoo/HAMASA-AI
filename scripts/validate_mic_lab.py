from html.parser import HTMLParser
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "mic-lab" / "index.html"


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.current = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.capture = True
            self.current = []

    def handle_data(self, data):
        if self.capture:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.capture:
            self.items.append("".join(self.current))
            self.capture = False


def main():
    html = PAGE.read_text(encoding="utf-8")
    parser = Scripts()
    parser.feed(html)
    assert len(parser.items) == 1, "Expected exactly one inline script"
    js = parser.items[0]
    required = [
        "navigator.mediaDevices.getUserMedia({ audio: true })",
        "window.isSecureContext",
        "context.resume()",
        "getByteTimeDomainData",
        "track.stop()",
        "addEventListener(\"pagehide\", cleanup)",
    ]
    for item in required:
        assert item in js, f"Missing required microphone safety behavior: {item}"
    forbidden = ["WebSocket(", "/api/live", "TTS_GEMINI_API_KEY", "window.HAMASA_CONFIG"]
    for item in forbidden:
        assert item not in js, f"Lab must remain isolated from chat/backend: {item}"
    subprocess.run(["node", "--check", "-"], input=js, text=True, check=True)
    print("PASS: microphone lab JavaScript syntax and isolation checks")


if __name__ == "__main__":
    main()
