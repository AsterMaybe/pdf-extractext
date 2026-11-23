# Consul Client Agent Configuration
# Used by: consul-agent-monolitico, consul-agent-go, consul-agent-db
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

# ---------------------------------------------------------------------------
# Service Definitions - Register Redis and MongoDB for service discovery
# These services run in the microservicio-db stack on the shared test_network
# NOTE: microservicio-db-go self-registers via code (main.go) to avoid conflicts
# ---------------------------------------------------------------------------
services = [
  {
    name    = "redis"
    id      = "redis-microservicio-db"
    port    = 6379
    tags    = ["redis", "cache", "microservicio-db"]
    address = "redis"  # Docker service name resolves via Docker DNS on test_network
    check = {
      id       = "redis-tcp-check"
      name     = "Redis TCP Health Check"
      tcp      = "redis:6379"
      interval = "10s"
      timeout  = "3s"
    }
  },
  {
    name    = "mongo"
    id      = "mongo-microservicio-db"
    port    = 27017
    tags    = ["mongodb", "database", "microservicio-db"]
    address = "mongo"  # Docker service name resolves via Docker DNS on test_network
    check = {
      id       = "mongo-tcp-check"
      name     = "MongoDB TCP Health Check"
      tcp      = "mongo:27017"
      interval = "10s"
      timeout  = "5s"
    }
  }
]