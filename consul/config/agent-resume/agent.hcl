# Consul Client Agent Configuration
# Used by: consul-agent-resume
# Version: Consul 2.1.0

# ---------------------------------------------------------------------------
# Basic Client Settings
# ---------------------------------------------------------------------------
datacenter = "dc1"
data_dir   = "/consul/data"
log_level  = "INFO"

# Run as client (not server)
server = false

# Bind to all interfaces
bind_addr = "0.0.0.0"

# Client interfaces: HTTP API, DNS, gRPC
client_addr = "0.0.0.0"

# ---------------------------------------------------------------------------
# Ports (client agents don't need server ports exposed)
# ---------------------------------------------------------------------------
ports {
  http     = 8500   # HTTP API (local only, for service registration)
  dns      = 8600   # DNS (for service discovery via DNS)
  grpc     = 8502   # gRPC
  serf_lan = 8301   # Serf LAN gossip
  # No serf_wan or server port on client
}

# ---------------------------------------------------------------------------
# Connect (Service Mesh) Configuration - DISABLED (not using mTLS)
# ---------------------------------------------------------------------------
# connect {
#   enabled = true
#   # Client agents inherit CA from server
# }

# ---------------------------------------------------------------------------
# ACL Configuration - DISABLED for now (enable with proper tokens in Phase 2)
# ---------------------------------------------------------------------------
# acl {
#   enabled = true
#   default_policy = "deny"
#   down_policy = "allow"
#   # Token provided via CONSUL_HTTP_TOKEN env var
# }

# ---------------------------------------------------------------------------
# DNS Configuration
# ---------------------------------------------------------------------------
dns_config {
  # Allow stale reads for better performance (eventual consistency)
  allow_stale = true
  # Max stale duration
  max_stale = "5s"
  # Enable service discovery via DNS SRV records
  enable_truncate = true
  # Only resolve services in this datacenter
  only_passing = true
}

# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
}

# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
limits {
  http_max_conns_per_client = 100
}

# ---------------------------------------------------------------------------
# Leave on Terminate (graceful deregistration)
# ---------------------------------------------------------------------------
leave_on_terminate = true