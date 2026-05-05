import os
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, g

app = Flask(__name__)

# ── startup state ──────────────────────────────────────────────
START_TIME = time.time()

MODE        = os.environ.get("MODE", "stable")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT    = int(os.environ.get("APP_PORT", 3000))

# ── chaos state (canary only) ──────────────────────────────────
# Stored in memory; reset on container restart.
chaos_lock  = threading.Lock()
chaos_state = {"mode": None, "duration": 0, "rate": 0.0}


def apply_chaos():
    """
    Called at the start of every request.
    If chaos is active, either sleeps or raises a 500.
    Returns (should_error: bool).
    """
    with chaos_lock:
        state = chaos_state.copy()

    if state["mode"] == "slow":
        time.sleep(state["duration"])
    elif state["mode"] == "error":
        if random.random() < state["rate"]:
            return True          # signal: return 500
    return False


def add_mode_header(response):
    """Attach X-Mode header when running in canary mode."""
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    return response


# ── routes ─────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    if MODE == "canary" and apply_chaos():
        resp = jsonify({"error": "chaos error injection", "code": 500})
        resp.status_code = 500
        return add_mode_header(resp)

    resp = jsonify({
        "message": f"Welcome to SwiftDeploy API",
        "mode":    MODE,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    return add_mode_header(resp)


@app.route("/healthz", methods=["GET"])
def healthz():
    uptime = round(time.time() - START_TIME, 2)
    resp = jsonify({"status": "ok", "uptime_seconds": uptime})
    return add_mode_header(resp)


@app.route("/chaos", methods=["POST"])
def chaos():
    # Chaos endpoint is only available in canary mode
    if MODE != "canary":
        resp = jsonify({"error": "chaos endpoint only available in canary mode"})
        resp.status_code = 403
        return resp

    data = request.get_json(silent=True) or {}
    chaos_mode = data.get("mode")

    with chaos_lock:
        if chaos_mode == "slow":
            duration = int(data.get("duration", 1))
            chaos_state.update({"mode": "slow", "duration": duration, "rate": 0.0})
            msg = f"Chaos mode set to slow ({duration}s delay)"

        elif chaos_mode == "error":
            rate = float(data.get("rate", 0.5))
            chaos_state.update({"mode": "error", "duration": 0, "rate": rate})
            msg = f"Chaos mode set to error (rate={rate})"

        elif chaos_mode == "recover":
            chaos_state.update({"mode": None, "duration": 0, "rate": 0.0})
            msg = "Chaos cleared — service recovering"

        else:
            resp = jsonify({"error": f"Unknown chaos mode: '{chaos_mode}'"})
            resp.status_code = 400
            return add_mode_header(resp)

    resp = jsonify({"status": "ok", "message": msg})
    return add_mode_header(resp)


# ── entrypoint ─────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)
