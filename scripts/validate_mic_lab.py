from html.parser import HTMLParser
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

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
    html = (ROOT / "mic-lab" / "index.html").read_text(encoding="utf-8")
    parser = Scripts()
    parser.feed(html)
    assert len(parser.items) == 1, "Expected one inline client script"
    js = parser.items[0]
    for item in ["navigator.mediaDevices.getUserMedia", 'fetch("/api/live-token"', "BidiGenerateContentConstrained", "realtimeInput", "audio/pcm;rate=16000", "inputTranscription", "outputTranscription", "stopPlayback()", "pagehide"]:
        assert item in js, f"Missing live voice behavior: {item}"
    for item in ["TTS_GEMINI_API_KEY", "AI_API_KEY", "window.HAMASA_CONFIG", "/api/chat"]:
        assert item not in js, f"Secret or main chat integration leaked: {item}"
    subprocess.run(["node", "--check", "-"], input=js, text=True, check=True)
    server = (ROOT / "mic-lab" / "server.py").read_text(encoding="utf-8")
    for item in ["GEMINI_API_KEY", "/v1alpha/auth_tokens", "newSessionExpireTime", "uses"]:
        assert item in server, f"Missing secure token provisioning: {item}"
    assert "API_KEY" not in html, "API key must never appear in browser page"
    print("PASS: Live client syntax, token isolation, audio streaming, cleanup checks")

if __name__ == "__main__":
    main()
