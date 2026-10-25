#!/usr/bin/env python3
"""Hook client. Stop: speak the headline (first line) of Claude's reply. --stop: cut speech off.
Uses a Kokoro daemon (voice af_heart) when KOKORO_PYTHON exists, else macOS say. SAY_HEADLINE=off mutes; SAY_VOICE overrides the voice."""
import json, os, re, socket, subprocess, sys, tempfile

SOCK = os.path.join(tempfile.gettempdir(), f"say-headline-{os.getuid()}.sock")
KOKORO_PY = os.environ.get("KOKORO_PYTHON", os.path.expanduser("~/.cache/tts-lab/.venv/bin/python"))
HERE = os.path.dirname(os.path.abspath(__file__))

def headline(text):
    in_insight = False
    for line in text.splitlines():
        if "★" in line:  # skip a whole Insight block: marker line, its text, and the closing rule
            in_insight = True
            continue
        if in_insight:
            in_insight = "─" not in line
            continue
        if not line.strip():
            continue
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)  # links -> text
        line = re.sub(r"^\s*(#+|[-*>]|\d+\.)\s*", "", line)     # heading/bullet markers
        line = re.sub(r"[*_`]", "", line).strip()
        if line:
            return line[:300]
    return ""

def send(req):
    s = socket.socket(socket.AF_UNIX); s.settimeout(2)
    try:
        s.connect(SOCK); s.sendall((json.dumps(req) + "\n").encode()); return True
    except OSError:
        return False
    finally:
        s.close()

def quiet(cmd, stderr=subprocess.DEVNULL):
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr, start_new_session=True)

def main():
    if "--stop" in sys.argv:
        send({"cmd": "stop"})
        subprocess.run(["pkill", "-x", "say"], capture_output=True)  # the fallback voice
        return
    if os.environ.get("SAY_HEADLINE") == "off":
        return
    msg = headline(json.load(sys.stdin).get("last_assistant_message", ""))
    if not msg:
        return
    if send({"cmd": "say", "text": msg}):
        return
    if os.path.exists(KOKORO_PY):  # first reply of the session (or idle timeout): start the daemon, it speaks the line itself
        log = open(os.path.join(tempfile.gettempdir(), "say-headline.log"), "a")
        quiet([KOKORO_PY, os.path.join(HERE, "daemon.py"), SOCK, msg], stderr=log)
    else:
        subprocess.run(["pkill", "-x", "say"], capture_output=True)
        quiet(["say", "-v", os.environ.get("SAY_FALLBACK_VOICE", "Tara"), "--", msg])

if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a voice glitch must never break the session
