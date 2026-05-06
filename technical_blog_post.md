# SwiftDeploy: Building a Deployment Tool That Writes Its Own Infrastructure

Most DevOps assignments ask you to hand-write infrastructure files. SwiftDeploy takes a different route: the only file an operator edits is `manifest.yaml`, and a CLI tool generates the rest.

This post walks through the full build: the declarative manifest, generated Docker Compose and Nginx config, the API service, Prometheus metrics, Open Policy Agent guardrails, chaos testing, and the audit trail.

By the end, you should be able to reproduce the project locally on a Windows machine with Docker and VS Code.

---

## The Design: One Manifest, Generated Infrastructure

The core idea behind SwiftDeploy is simple:

```text
manifest.yaml -> swiftdeploy init -> docker-compose.yml + nginx.conf
```

`manifest.yaml` is the single source of truth. It describes the service image, service port, Nginx image and port, network settings, OPA settings, restart policy, log volume, app version, deployment mode, and policy thresholds.

Example:

```yaml
services:
  image: swift-deploy-1-node:latest
  port: 3000
  mode: stable
  app_version: "1.0.0"
  restart_policy: unless-stopped
  log_volume: swiftdeploy-logs

nginx:
  image: nginx:latest
  port: 8080
  proxy_timeout: 30

opa:
  image: openpolicyagent/opa:latest-rootless
  port: 8181

policy:
  infrastructure:
    min_disk_free_gb: 10.0
    max_cpu_load: 2.0
    min_mem_free_percent: 10.0
  canary:
    max_error_rate_percent: 1.0
    max_p99_latency_ms: 500
    min_sample_size: 10

network:
  name: swiftdeploy-net
  driver_type: bridge

contact: "devops@swiftdeploy.local"
```

The CLI is an executable Python script named `swiftdeploy`. Its `init` command reads the manifest, substitutes values into templates, and writes:

- `docker-compose.yml`
- `nginx.conf`

That means generated files can be deleted and recreated at any time:

```powershell
python swiftdeploy init
```

This is useful because the deploy state is not hidden in multiple config files. If I need to change the app port, deployment mode, restart policy, OPA port, or policy threshold, I change the manifest and regenerate.

---

## The API Service

The service is a Flask application packaged as a Docker image. It runs in either `stable` or `canary` mode using the `MODE` environment variable injected by Docker Compose.

It exposes:

```text
GET  /         -> welcome response with mode, version, and timestamp
GET  /healthz  -> liveness response with uptime
GET  /metrics  -> Prometheus text metrics
POST /chaos    -> canary-only chaos controls
```

In canary mode, the service adds:

```text
X-Mode: canary
```

The same Docker image runs both modes. Promotion does not rebuild the image; it updates `manifest.yaml`, regenerates Compose, and restarts only the service container.

---

## Nginx as the Only Public Ingress

The service port is never exposed directly to the host. Docker Compose uses `expose` for the app container, while Nginx is the only public ingress.

Nginx:

- listens on `nginx.port`
- proxies traffic to the internal service
- forwards `X-Mode` from upstream
- adds `X-Deployed-By: swiftdeploy`
- writes access logs in the required format
- returns JSON bodies for `502`, `503`, and `504`

The required log format is generated into `nginx.conf`:

```nginx
log_format swiftdeploy_fmt '$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request';
```

OPA is not routed through Nginx. Public traffic on the Nginx port goes to the app backend only.

---

## The Guardrails: OPA as the Policy Brain

Stage 4B adds the "Brain" of the system: Open Policy Agent.

SwiftDeploy includes an OPA sidecar in the generated Docker Compose file. OPA loads all `.rego` files from the `policies/` directory:

```yaml
opa:
  image: ${OPA_IMAGE}
  ports:
    - "${OPA_PORT}:${OPA_PORT}"
  volumes:
    - ./policies:/policies:ro
  command:
    - "run"
    - "--server"
    - "--addr=0.0.0.0:${OPA_PORT}"
    - "--log-level=error"
    - "/policies"
```

OPA is reachable by the CLI on the host, but it is isolated from the public Nginx ingress. This matters because OPA exposes a policy API. That API is useful for the deployment tool, but it should not be available to normal application users through the public web port.

I wrote two separate policy domains:

```text
policies/
  infrastructure.rego
  canary.rego
```

Each domain answers one question.

### Infrastructure Policy

The infrastructure policy answers:

> Is this host safe enough to deploy onto?

It denies deployment when:

- disk free is below `10GB`
- CPU load is above `2.0`
- free memory is below the configured threshold

The Rego file does not hardcode the thresholds. The thresholds come from `manifest.yaml` and are uploaded to OPA as data before the decision is queried.

Example decision reason:

```text
Disk free (4.2GB) is below minimum (10.0GB)
```

### Canary Safety Policy

The canary policy answers:

> Is the current canary healthy enough to promote?

It denies promotion when:

- error rate is above `1%`
- P99 latency is above `500ms`
- the traffic sample is too small

For promotion, SwiftDeploy scrapes `/metrics` twice over a 30-second window, calculates error rate and P99 latency from the delta, then sends that context to OPA.

That distinction is important: pre-deploy and pre-promote are different questions, so they send different inputs to different policy domains.

---

## Gated Lifecycle

SwiftDeploy supports:

```text
init
validate
deploy
promote canary
promote stable
status
audit
teardown
```

The deploy flow is gated:

```text
swiftdeploy deploy
  -> generate configs
  -> start OPA sidecar
  -> collect host stats
  -> ask OPA infrastructure policy
  -> if denied, block before app/Nginx start
  -> if allowed, start app and Nginx
  -> wait for /healthz
```

The promote flow is also gated:

```text
swiftdeploy promote canary
  -> scrape /metrics
  -> wait 30 seconds
  -> scrape /metrics again
  -> calculate error rate and P99 latency
  -> ask OPA canary policy
  -> if denied, block promotion
  -> if allowed, update manifest.yaml
  -> regenerate docker-compose.yml
  -> restart service container only
  -> confirm /healthz
```

The CLI surfaces OPA reasoning directly, so the operator sees why something was allowed or denied.

---

## Observability: Prometheus Metrics

The API exposes `/metrics` in Prometheus text format.

It tracks:

```text
http_requests_total{method,path,status_code}
http_request_duration_seconds_bucket{method,path,le}
app_uptime_seconds
app_mode
chaos_active
```

`app_mode` is:

```text
0 = stable
1 = canary
```

`chaos_active` is:

```text
0 = none
1 = slow
2 = error
```

The `swiftdeploy status` command scrapes these metrics repeatedly and renders a live terminal dashboard showing:

- mode
- uptime
- chaos state
- requests per second
- error rate
- P99 latency
- infrastructure policy result
- canary policy result

Each status scrape is appended to `history.jsonl`, which later powers the audit report.

---

## The Chaos: Slow and Error Injection

Chaos is only available in canary mode. First, I promoted to canary:

```powershell
python swiftdeploy promote canary
```

Then I enabled slow responses:

```powershell
curl.exe -X POST http://localhost:8080/chaos `
  -H "Content-Type: application/json" `
  -d "{\"mode\":\"slow\",\"duration\":2}"
```

Requests to `/` became slower because the app slept before responding.

Then I tested error injection:

```powershell
curl.exe -X POST http://localhost:8080/chaos `
  -H "Content-Type: application/json" `
  -d "{\"mode\":\"error\",\"rate\":0.5}"
```

I generated traffic:

```powershell
1..20 | ForEach-Object {
  curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:8080/
}
```

The status dashboard showed the failure clearly:

```text
SwiftDeploy Status

App Metrics
  Mode:          canary
  Uptime:        154s
  Chaos:         error
  Req/s:         1.80
  Error rate:    45.0%
  P99 latency:   500ms
  Total reqs:    42

Policy Compliance
  infrastructure: [PASS]  All checks passed
  canary:         [FAIL]  Error rate (45.00%) exceeds maximum allowed (1.00%)

Policy violations detected - check reasons above
```

This is the main point of the chaos test: the system should not silently continue as if everything is fine. The metrics show degradation, the policy detects it, and promotion is blocked with a reason.

Recovery is simple:

```powershell
curl.exe -X POST http://localhost:8080/chaos `
  -H "Content-Type: application/json" `
  -d "{\"mode\":\"recover\"}"
```

---

## Auditing: The Memory

The audit command parses `history.jsonl` and writes `audit_report.md`:

```powershell
python swiftdeploy audit
```

The report contains:

- a timeline of deploys, promotions, policy checks, and chaos transitions
- a policy violations section
- a status scrape summary

Example:

```markdown
## Policy Violations

| Timestamp | Policy Domain | Reason |
|-----------|--------------|--------|
| `2026-05-06 16:49:06` | `canary` | Insufficient traffic sample (0 requests). Need at least 10 to make a safe decision. |
```

The report is valid GitHub Flavored Markdown, including escaped table content for policy messages.

---

## How to Reproduce

From VS Code on Windows, open the project root and run:

```powershell
cd C:\Users\hords\Documents\GitHub\swiftdeploy
```

Build the API image:

```powershell
docker build -t swift-deploy-1-node:latest ./app
```

Generate infrastructure files:

```powershell
python swiftdeploy init
```

Validate:

```powershell
python swiftdeploy validate
```

Deploy:

```powershell
python swiftdeploy deploy
```

Test endpoints:

```powershell
curl.exe http://localhost:8080/
curl.exe http://localhost:8080/healthz
curl.exe http://localhost:8080/metrics
```

Confirm OPA is not exposed through Nginx:

```powershell
curl.exe -i http://localhost:8080/v1/data
```

Confirm OPA is reachable by the CLI/host:

```powershell
curl.exe http://localhost:8181/health
```

Run the dashboard:

```powershell
python swiftdeploy status
```

Promote to canary:

```powershell
python swiftdeploy promote canary
```

Inject chaos:

```powershell
curl.exe -X POST http://localhost:8080/chaos `
  -H "Content-Type: application/json" `
  -d "{\"mode\":\"error\",\"rate\":0.5}"
```

Generate traffic:

```powershell
1..20 | ForEach-Object {
  curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:8080/
}
```

Recover:

```powershell
curl.exe -X POST http://localhost:8080/chaos `
  -H "Content-Type: application/json" `
  -d "{\"mode\":\"recover\"}"
```

Generate the audit report:

```powershell
python swiftdeploy audit
```

Tear everything down:

```powershell
python swiftdeploy teardown --clean
```

---

## Lessons Learned

The biggest lesson is that a deployment tool should be predictable. When configuration is scattered across many hand-edited files, it is easy for the source of truth to drift. SwiftDeploy avoids that by making `manifest.yaml` the only file operators edit.

The second lesson is that observability and policy work best together. Metrics tell us what is happening, but policy decides whether the system should continue. Prometheus gives SwiftDeploy eyes; OPA gives it a brain.

The third lesson is that policy should explain itself. A bare `false` is not useful during an incident. A message like `Disk free (4.2GB) is below minimum (10.0GB)` immediately tells the operator what went wrong.

Finally, isolation matters. OPA is powerful, but its API should not be exposed through the public Nginx port. The CLI can reach OPA to make deployment decisions, while users only reach the app through Nginx.

SwiftDeploy started as a small manifest generator, but by adding metrics, OPA policies, status monitoring, chaos testing, and auditing, it became a safer deployment workflow: one that can explain what it is doing, refuse unsafe changes, and leave behind a readable trail of what happened.
