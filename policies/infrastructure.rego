package swiftdeploy.infrastructure

default allow = false

allow {
    count(deny) == 0
}

deny[msg] {
    input.disk_free_gb < data.infrastructure.min_disk_free_gb
    msg = sprintf("Disk free (%.1fGB) is below minimum (%.1fGB)", [input.disk_free_gb, data.infrastructure.min_disk_free_gb])
}

deny[msg] {
    input.cpu_load > data.infrastructure.max_cpu_load
    msg = sprintf("CPU load (%.2f) exceeds maximum (%.2f)", [input.cpu_load, data.infrastructure.max_cpu_load])
}
