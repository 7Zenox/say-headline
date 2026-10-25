#!/usr/bin/env python3
"""Runnable end-to-end check for say-headline. Plays real audio. Usage: python3 tests/check.py"""
import json, os, subprocess, sys, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import speak

SPEAK = os.path.join(os.path.dirname(__file__), "..", "scripts", "speak.py")
SOCK = speak.SOCK
fails = []

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
    if not ok: fails.append(name)

def run(payload, env=None, args=()):
    e = {**os.environ, **(env or {})}
    t = time.time()
    p = subprocess.run([sys.executable, SPEAK, *args], input=payload if isinstance(payload, str) else json.dumps(payload), text=True, capture_output=True, env=e)
    return p, time.time() - t

def running(name):
    return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0

def wait_for(name, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        if running(name): return time.time() - t
        time.sleep(0.05)
    return None

def wait_gone(name, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        if not running(name): return True
        time.sleep(0.1)
    return False

def kill_all():
    subprocess.run(["pkill", "-f", "say-headline.*daemon.py|scripts/daemon.py"], capture_output=True)
    subprocess.run(["pkill", "-x", "afplay"], capture_output=True)
    subprocess.run(["pkill", "-x", "say"], capture_output=True)
    if os.path.exists(SOCK):
        try: os.unlink(SOCK)
        except OSError: pass
    time.sleep(1)

# 1. headline extraction
H = speak.headline
check("skips insight block + blank, strips markdown", H("`★ Insight ─────`\ninsight text\nmore text\n`──────────`\n\n**Done:** see [docs](http://a), ok.\n- b") == "Done: see docs, ok.")
check("insight block after the headline is ignored", H("Done. Fine.\n`★ Insight ───`\nx\n`───`") == "Done. Fine.")
check("bullet-only message", H("- first bullet\n- second") == "first bullet")
check("empty message", H("") == "" and H("\n\n") == "")
check("truncates to 300", len(H("a" * 500)) == 300)

# 2. malformed / muted input never crashes or speaks
kill_all()
p, _ = run("not json")
check("malformed stdin exits 0, silent", p.returncode == 0 and not running("say") and not running("afplay"))
p, _ = run({"last_assistant_message": "muted test"}, env={"SAY_HEADLINE": "off"})
time.sleep(1.5)
check("SAY_HEADLINE=off is silent", p.returncode == 0 and not os.path.exists(SOCK) and not running("afplay") and not running("say"))

# 3. cold start: daemon launches and speaks
p, hook_t = run({"last_assistant_message": "Done. The cold start test is speaking with Kokoro."})
t = wait_for("afplay", 40)
check("hook returns fast (does not block on model load)", hook_t < 1.0, f"{hook_t:.2f}s")
check("cold start: audio begins", t is not None, f"{t:.1f}s after hook" if t else "")
check("daemon socket exists", os.path.exists(SOCK))
wait_gone("afplay", 30)

# 4. warm path
p, hook_t = run({"last_assistant_message": "Warm path, second line."})
t = wait_for("afplay", 15)
check("warm: audio begins quickly", t is not None and t < 6, f"{t:.1f}s" if t else "")

# 5. interrupt: a newer message replaces the one playing
time.sleep(0.3)
run({"last_assistant_message": "This is a deliberately long headline that goes on for quite a while so that it is still playing when the next one arrives to interrupt it."})
wait_for("afplay", 15); time.sleep(0.5)
pid1 = subprocess.run(["pgrep", "-x", "afplay"], capture_output=True, text=True).stdout.split()
run({"last_assistant_message": "Interrupted. This replaced the long one."})
t0, pid2 = time.time(), []
while time.time() - t0 < 10:  # the replacement must actually start playing under a NEW player
    pid2 = subprocess.run(["pgrep", "-x", "afplay"], capture_output=True, text=True).stdout.split()
    if pid2 and pid2 != pid1: break
    time.sleep(0.1)
check("interrupt: replacement plays, old player gone", bool(pid1) and bool(pid2) and pid2 != pid1 and len(pid2) == 1, f"before={pid1} after={pid2}")
wait_gone("afplay", 30)

# 6. --stop cuts speech off
run({"last_assistant_message": "This headline is long enough that the stop command must cut it off before the end of the sentence."})
wait_for("afplay", 15); time.sleep(0.5)
run("", args=("--stop",))
time.sleep(0.5)
check("--stop kills playback", not running("afplay"))

# 7. stop during synthesis cancels the pending line
run({"last_assistant_message": "This line should never be heard because stop arrives during synthesis."})
time.sleep(0.2)
run("", args=("--stop",))
time.sleep(4)
check("--stop during synthesis: nothing plays", not running("afplay"))

# 8. fallback to say when Kokoro is unavailable
kill_all()
p, _ = run({"last_assistant_message": "Fallback voice test."}, env={"KOKORO_PYTHON": "/nonexistent/python"})
t = wait_for("say", 5)
check("fallback: macOS say used when Kokoro missing", t is not None and not os.path.exists(SOCK))
wait_gone("say", 15)

# 9. idle exit
kill_all()
env = {**os.environ, "SAY_IDLE": "6"}
subprocess.run([sys.executable, SPEAK], input=json.dumps({"last_assistant_message": "Idle test."}), text=True, env=env)
wait_for("afplay", 40); wait_gone("afplay", 20)
time.sleep(14)
check("idle: daemon exits and removes socket", not os.path.exists(SOCK))

kill_all()
print("\nALL PASSED" if not fails else f"\nFAILED: {fails}")
sys.exit(1 if fails else 0)
