import os
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, g
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)

# ── startup state ──────────────────────────────────────────────
START_TIME  = time.time()
MODE        = os.environ.get("MODE", "stable")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT    = int(os.environ.get("APP_PORT", 3000))

# ── chaos state ────────────────────────────────────────────────
chaos_lock  = threading.Lock()
chaos_state = {"mode": None, "duration": 0, "rate": 0.0}

# ── prometheus metrics ─────────────────────────────────────────
# Counter: goes up only, never down. Tracks total requests.
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"]
)

# Histogram: records how long each request took.
# buckets are in seconds — these are the standard Prometheus buckets.
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Gauges: can go up or down. Track current state.
UPTIME_GAUGE = Gauge(
    "app_uptime_seconds",
    "Seconds since the app started"
)
MODE_GAUGE = Gauge(
    "app_mode",
    "Current app mode: 0=stable, 1=canary"
)
CHAOS_GAUGE = Gauge(
    "chaos_active",
    "Active chaos mode: 0=none, 1=slow, 2=error"
)

# Set initial gauge values
MODE_GAUGE.set(1 if MODE == "canary" else 0)
CHAOS_GAUGE.set(0)


# ── request tracking hooks ─────────────────────────────────────
@app.before_request
def start_timer():
    """Record the start time of every request."""
    g.start_time = time.time()


@app.after_request
def track_request(response):
    """
    After every request completes:
    - Record how long it took (histogram)
    - Increment the request counter with method, path, status
    - Update uptime and state gauges
    Skip /metrics itself to avoid tracking the tracker.
    """
    if request.path == "/metrics":
        return response

    duration = time.time() - g.start_time

    REQUEST_DURATION.labels(
        method=request.method,
        path=request.path
    ).observe(duration)

    REQUEST_COUNT.labels(
        method=request.method,
        path=request.path,
        status_code=str(response.status_code)
    ).inc()

    # Update live gauges
    UPTIME_GAUGE.set(time.time() - START_TIME)
    MODE_GAUGE.set(1 if MODE == "canary" else 0)

    with chaos_lock:
        cm = chaos_state["mode"]
    if cm == "slow":
        CHAOS_GAUGE.set(1)
    elif cm == "error":
        CHAOS_GAUGE.set(2)
    else:
        CHAOS_GAUGE.set(0)

    return response


# ── chaos helpers ──────────────────────────────────────────────
def apply_chaos():
    with chaos_lock:
        state = chaos_state.copy()
    if state["mode"] == "slow":
        time.sleep(state["duration"])
    elif state["mode"] == "error":
        if random.random() < state["rate"]:
            return True
    return False


def add_mode_header(response):
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
        "message": "Welcome to SwiftDeploy API",
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


@app.route("/metrics", methods=["GET"])
def metrics():
    """
    Expose Prometheus metrics in text format.
    This is scraped by swiftdeploy status and pre-promote checks.
    """
    # Update uptime gauge fresh on every scrape
    UPTIME_GAUGE.set(time.time() - START_TIME)

    from flask import Response
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# ── entrypoint ─────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)
