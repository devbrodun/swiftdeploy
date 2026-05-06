# SwiftDeploy Audit Report

Generated: 2026-05-06 17:26:24 UTC
Events processed: 12

---

## Timeline

| Timestamp | Event | Detail |
|-----------|-------|--------|
| `2026-05-06 11:56:06` | Pre-Deploy Check | Infrastructure policy: **FAIL** |
| `2026-05-06 16:46:25` | Pre-Deploy Check | Infrastructure policy: **PASS** |
| `2026-05-06 16:46:25` | Deploy | Stack deployed - status: success |
| `2026-05-06 16:49:06` | Pre-Promote Check | Canary policy: **FAIL** |
| `2026-05-06 16:50:04` | Promote | Mode switched to **stable** |
| `2026-05-06 17:25:19` | Pre-Deploy Check | Infrastructure policy: **PASS** |
| `2026-05-06 17:25:27` | Deploy | Stack deployed - status: success |

---

## Policy Violations

| Timestamp | Policy Domain | Reason |
|-----------|--------------|--------|
| `2026-05-06 11:56:06` | `infrastructure` | OPA data upload failed: &lt;urlopen error [WinError 10061] No connection could be made because the target machine actively refused it&gt; |
| `2026-05-06 16:49:06` | `canary` | Insufficient traffic sample (0 requests). Need at least 10 to make a safe decision. |

---

## Status Scrape Summary

- Total scrapes: **5**
- Average req/s: **0.0**
- Average error rate: **0.0%**
- Average P99 latency: **0.0ms**
- Scrapes with chaos active: **0**
