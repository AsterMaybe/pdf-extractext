# Consul Server Configuration (dev/bootstrap mode) - MINIMAL
# Used by: consul service in docker-compose.consul.yml
# Version: Consul 2.1.0

# ---------------------------------------------------------------------------
# Basic Server Settings
# ---------------------------------------------------------------------------
datacenter = "dc1"
data_dir   = "/consul/data"
log_level  = "INFO"

# Dev mode: single server, bootstrap, no persistence required for elections
bootstrap = true
server    = true

# Bind to all interfaces so clients can reach us
bind_addr = "0.0.0.0"

# Client interfaces: HTTP API, DNS, gRPC
client_addr = "0.0.0.0"

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------
ports {
  http     = 8500
  dns      = 8600
  grpc     = 8502
  serf_lan = 8301
  serf_wan = 8302
  server   = 8300
}

# ---------------------------------------------------------------------------
# UI Configuration
# ---------------------------------------------------------------------------
ui_config {
  enabled = true
}

# ---------------------------------------------------------------------------
# Connect (Service Mesh) Configuration - DISABLED (not using mTLS)
# ---------------------------------------------------------------------------
# connect {
#   enabled = true
# }

# ---------------------------------------------------------------------------
# ACL (Access Control) Configuration - DISABLED for now
# ---------------------------------------------------------------------------
# acl {
#   enabled = true
#   default_policy = "deny"
#   down_policy = "allow"
#   tokens {
#     initial_management = "dev-bootstrap-token"
#   }
# }

# ---------------------------------------------------------------------------
# Performance / Limits
# ---------------------------------------------------------------------------
limits {
  http_max_conns_per_client = 200
}

# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
}