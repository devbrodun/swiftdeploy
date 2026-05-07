package swiftdeploy.canary

default allow = false

allow {
    count(deny) == 0
}

deny[msg] {
    input.error_rate_percent > data.canary.max_error_rate_percent
    msg = sprintf("Error rate (%.2f%%) exceeds maximum allowed (%.2f%%)", [input.error_rate_percent, data.canary.max_error_rate_percent])
}

deny[msg] {
    input.p99_latency_ms > data.canary.max_p99_latency_ms
    msg = sprintf("P99 latency (%dms) exceeds maximum allowed (%dms)", [input.p99_latency_ms, data.canary.max_p99_latency_ms])
}
