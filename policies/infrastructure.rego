package swiftdeploy.infrastructure

# Thresholds come from manifest.yaml and are uploaded to data.infrastructure.

default allow = false

allow {
    count(deny) == 0
}

deny[reason] {
    input.disk_free_gb < data.infrastructure.min_disk_free_gb
    reason := sprintf(
        "Disk free (%.1fGB) is below minimum (%.1fGB)",
        [input.disk_free_gb, data.infrastructure.min_disk_free_gb]
    )
}

deny[reason] {
    input.cpu_load > data.infrastructure.max_cpu_load
    reason := sprintf(
        "CPU load (%.2f) exceeds maximum (%.2f)",
        [input.cpu_load, data.infrastructure.max_cpu_load]
    )
}

deny[reason] {
    input.mem_free_percent < data.infrastructure.min_mem_free_percent
    reason := sprintf(
        "Free memory (%.1f%%) is below minimum (%.1f%%)",
        [input.mem_free_percent, data.infrastructure.min_mem_free_percent]
    )
}
