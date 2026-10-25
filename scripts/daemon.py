#!/usr/bin/env python3
"""Kokoro speaker daemon: keeps the model loaded, speaks lines sent over a unix socket, stops on request.
Protocol: one JSON line per connection: {"cmd":"say","text":...} | {"cmd":"stop"}. Exits after IDLE seconds unused."""
import json, os, socket, subprocess, sys, tempfile, threading, time, warnings
warnings.filterwarnings("ignore")
import spacy
spacy.load = lambda *a, **k: spacy.blank("en")  # the spaCy model load is broken on current wheels; blank English is enough for Kokoro's G2P
import numpy as np, soundfile as sf
from kokoro import KPipeline

SOCK, VOICE, IDLE = sys.argv[1], os.environ.get("SAY_VOICE", "af_heart"), int(os.environ.get("SAY_IDLE", "1800"))
pipe = KPipeline(lang_code="b" if VOICE.startswith("b") else "a", repo_id="hexgrad/Kokoro-82M")
gen, player, lock, last = 0, None, threading.Lock(), time.time()

def stop():
    global gen, player
    with lock:
        gen += 1  # invalidates any synthesis still in flight
        if player and player.poll() is None:
            player.kill()

def say(text):
    global player
    stop()
    me = gen
    audio = np.concatenate([a for _, _, a in pipe(text, voice=VOICE)])
    with lock:
        if me != gen:  # a newer say/stop arrived while we were synthesizing
            return
        wav = os.path.join(tempfile.gettempdir(), f"say-headline-{os.getuid()}.wav")
        sf.write(wav, audio, 24000)
        player = subprocess.Popen(["afplay", wav], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def handle(conn):
    global last
    last = time.time()
    try:
        req = json.loads(conn.makefile().readline())
        if req.get("cmd") == "stop":
            stop()
        elif req.get("cmd") == "say" and req.get("text"):
            threading.Thread(target=say, args=(req["text"],), daemon=True).start()
    except Exception:
        pass
    finally:
        conn.close()

if os.path.exists(SOCK):
    probe = socket.socket(socket.AF_UNIX)
    try:
        probe.connect(SOCK); sys.exit(0)  # another daemon is already serving
    except OSError:
        os.unlink(SOCK)  # stale socket
srv = socket.socket(socket.AF_UNIX); srv.bind(SOCK); srv.listen(8); srv.settimeout(5)
os.chmod(SOCK, 0o600)
if len(sys.argv) > 2:
    say(sys.argv[2])  # the line that triggered the start
try:
    while time.time() - last < IDLE:
        try:
            c, _ = srv.accept()
        except socket.timeout:
            continue
        handle(c)
finally:
    stop()
    try: os.unlink(SOCK)
    except OSError: pass
