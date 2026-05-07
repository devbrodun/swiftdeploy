# SwiftDeploy Audit Report

Generated: 2026-05-07 13:02:49 UTC
Events processed: 5

---

## Timeline

| Timestamp | Event | Detail |
|-----------|-------|--------|
| `2026-05-07 12:57:56` | Pre-Deploy Check | Infrastructure policy: **PASS** |
| `2026-05-07 12:58:07` | Deploy | Stack deployed - status: success |
| `2026-05-07 13:01:41` | Pre-Promote Check | Canary policy: **FAIL** |

---

## Policy Violations

| Timestamp | Policy Domain | Reason |
|-----------|--------------|--------|
| `2026-05-07 13:01:41` | `canary` | Insufficient traffic sample (0 requests). Need at least 10. |

---

## Status Scrape Summary

- Total scrapes: **2**
- Average req/s: **-0.08**
- Average error rate: **0.0%**
- Average P99 latency: **2.5ms**
- Scrapes with chaos active: **0**
