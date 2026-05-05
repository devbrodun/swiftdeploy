# SwiftDeploy

A declarative deployment CLI that generates all infrastructure config from a single `manifest.yaml`.

---

## How It Works

```
manifest.yaml  ──►  swiftdeploy init  ──►  nginx.conf
                                      ──►  docker-compose.yml
                                      
swiftdeploy deploy    → starts the full stack
swiftdeploy validate  → 5 pre-flight checks
swiftdeploy promote   → switches stable ↔ canary
swiftdeploy teardown  → removes everything
```

`manifest.yaml` is the **only file you ever edit**. Every other config is generated.

---

## Project Structure

```
swiftdeploy/
├── manifest.yaml                  # Single source of truth
├── swiftdeploy                    # CLI executable (Python)
├── app/
│   ├── main.py                    # Flask API service
│   ├── requirements.txt
│   └── Dockerfile
├── templates/
│   ├── nginx.conf.template        # Nginx template
│   └── docker-compose.yml.template
├── nginx.conf                     # Generated — do not edit
├── docker-compose.yml             # Generated — do not edit
└── README.md
```

---

## Prerequisites

- Docker + Docker Compose v2 (`docker compose`)
- Python 3.8+
- PyYAML: `pip install pyyaml`

---

## Setup & First Run

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/swiftdeploy.git
cd swiftdeploy
```

### 2. Build the app image

The image name must match `services.image` in `manifest.yaml`.

```bash
docker build -t swift-deploy-1-node:latest ./app
```

### 3. Make the CLI executable

```bash
chmod +x swiftdeploy
```

---

## Subcommand Walkthrough

### `swiftdeploy init`

Parses `manifest.yaml` and generates `nginx.conf` and `docker-compose.yml` from templates.

```bash
./swiftdeploy init
```

Nothing needs to be running. Safe to run multiple times (idempotent).

---

### `swiftdeploy validate`

Runs 5 pre-flight checks before you attempt a deploy:

| # | Check |
|---|-------|
| 1 | `manifest.yaml` exists and is valid YAML |
| 2 | All required fields are present and non-empty |
| 3 | Docker image referenced in manifest exists locally |
| 4 | Nginx port is not already bound on the host |
| 5 | Generated `nginx.conf` is syntactically valid |

```bash
./swiftdeploy validate
```

Exits `0` if all pass, non-zero if any fail.

---

### `swiftdeploy deploy`

Runs `init`, brings up the full stack, and blocks until `/healthz` passes or 60s timeout.

```bash
./swiftdeploy deploy
```

Once complete, the API is available at:
- `http://localhost:8080/`       → welcome message
- `http://localhost:8080/healthz` → health check

---

### `swiftdeploy promote [canary|stable]`

Switches the deployment mode with a rolling service restart:

```bash
./swiftdeploy promote canary
./swiftdeploy promote stable
```

What it does:
1. Updates `mode` in `manifest.yaml` in-place
2. Regenerates `docker-compose.yml` with the new `MODE` env var
3. Restarts **only** the service container (nginx keeps running)
4. Confirms the new mode by hitting `/healthz` and reading `X-Mode` header

---

### `swiftdeploy teardown`

Removes all containers, networks, and named volumes:

```bash
./swiftdeploy teardown
```

With `--clean`, also deletes `nginx.conf` and `docker-compose.yml`:

```bash
./swiftdeploy teardown --clean
```

---

## API Endpoints

### `GET /`

Returns welcome message with current mode, version, and timestamp.

```json
{
  "message": "Welcome to SwiftDeploy API",
  "mode": "stable",
  "version": "1.0.0",
  "timestamp": "2026-05-05T10:00:00+00:00"
}
```

### `GET /healthz`

```json
{ "status": "ok", "uptime_seconds": 42.3 }
```

### `POST /chaos` *(canary mode only)*

Simulate degraded behaviour:

```bash
# Slow responses (sleep 5s before every reply)
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"slow","duration":5}'

# Random 500 errors (~50% of requests)
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"error","rate":0.5}'

# Recover to normal
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"recover"}'
```

Returns `403` if called in stable mode.

---

## manifest.yaml Reference

```yaml
services:
  image: swift-deploy-1-node:latest   # Docker image name
  port: 3000                          # Port the app listens on inside container
  mode: stable                        # stable or canary (updated by promote)
  app_version: "1.0.0"               # Injected as APP_VERSION env var
  restart_policy: unless-stopped      # Docker restart policy
  log_volume: swiftdeploy-logs        # Named volume for logs

nginx:
  image: nginx:latest
  port: 8080                          # Public-facing port on the host
  proxy_timeout: 30                   # Seconds before nginx gives up on upstream

network:
  name: swiftdeploy-net
  driver_type: bridge

contact: "devops@swiftdeploy.local"   # Shown in JSON error bodies
```

---

## Security Highlights

- Containers run as **non-root user** (`appuser`, UID 1000)
- All Linux capabilities dropped (`cap_drop: [ALL]`)
- `no-new-privileges: true` on all containers
- App port never exposed to host — all traffic routes through Nginx
- Alpine-based image keeps final size well under 300MB

---

## Nginx Access Log Format

```
$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request
```

Example:
```
2026-05-05T10:00:01+00:00 | 200 | 0.002s | 172.18.0.2:3000 | GET / HTTP/1.1
```
