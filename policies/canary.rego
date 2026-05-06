package swiftdeploy.canary

# Thresholds come from manifest.yaml and are uploaded to data.canary.

default allow = false

allow {
    count(deny) == 0
}

deny[reason] {
    input.error_rate_percent > data.canary.max_error_rate_percent
    reason := sprintf(
        "Error rate (%.2f%%) exceeds maximum allowed (%.2f%%)",
        [input.error_rate_percent, data.canary.max_error_rate_percent]
    )
}

deny[reason] {
    input.p99_latency_ms > data.canary.max_p99_latency_ms
    reason := sprintf(
        "P99 latency (%dms) exceeds maximum allowed (%dms)",
        [input.p99_latency_ms, data.canary.max_p99_latency_ms]
    )
}

deny[reason] {
    input.sample_size < data.canary.min_sample_size
    reason := sprintf(
        "Insufficient traffic sample (%d requests). Need at least %d to make a safe decision.",
        [input.sample_size, data.canary.min_sample_size]
    )
}
