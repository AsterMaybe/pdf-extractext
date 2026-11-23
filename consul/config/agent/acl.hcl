# Consul ACL Configuration
# Bootstrap token and service-specific policies
# Version: Consul 2.1.0
#
# This file defines:
# 1. Bootstrap token (management) - for initial setup only
# 2. Service-specific tokens with least-privilege policies
#
# IMPORTANT: In production, use Docker secrets or Vault for tokens!
# For dev, tokens are in .env file (gitignored).

# ---------------------------------------------------------------------------
# Bootstrap Token (Management)
# ---------------------------------------------------------------------------
# This token has full cluster access. Use ONLY for initial setup.
# Set via CONSUL_BOOTSTRAP_TOKEN in .env (default: dev-bootstrap-token)
#
# To create additional tokens after bootstrap:
#   consul acl token create -description "monolitico" -policy-name "monolitico-policy"
#   consul acl token create -description "microservicio-go" -policy-name "microservicio-go-policy"
#   consul acl token create -description "microservicio-db" -policy-name "microservicio-db-policy"

# ---------------------------------------------------------------------------
# Policies (apply via Consul UI or CLI after bootstrap)
# ---------------------------------------------------------------------------

# ========================================================================
# Policy: monolitico-policy
# Allows: service registration, health checks, KV config read, service discovery
# ========================================================================
# Name: "monolitico-policy"
# Description: "Policy for monolitico (FastAPI orchestrator)"
# Rules:
#   service "monolitico" {
#     policy = "write"  # register, deregister, health checks
#   }
#   service "microservicio-go" {
#     policy = "read"   # discover, health checks
#   }
#   service "microservicio-db" {
#     policy = "read"   # discover, health checks
#   }
#   node_prefix "" {
#     policy = "read"   # list nodes for debugging
#   }
#   key_prefix "config/monolitico/" {
#     policy = "read"   # read own config
#   }
#   key_prefix "config/shared/" {
#     policy = "read"   # read shared config
#   }
#   session_prefix "" {
#     policy = "write"  # for leader election, locks
#   }

# ========================================================================
# Policy: microservicio-go-policy
# ========================================================================
# Name: "microservicio-go-policy"
# Description: "Policy for microservicio-go (PDF extractor)"
# Rules:
#   service "microservicio-go" {
#     policy = "write"
#   }
#   service "redis" {
#     policy = "read"
#   }
#   node_prefix "" {
#     policy = "read"
#   }
#   key_prefix "config/microservicio-go/" {
#     policy = "read"
#   }
#   key_prefix "config/shared/" {
#     policy = "read"
#   }
#   session_prefix "" {
#     policy = "write"
#   }

# ========================================================================
# Policy: microservicio-db-policy
# ========================================================================
# Name: "microservicio-db-policy"
# Description: "Policy for microservicio-db (Document CRUD)"
# Rules:
#   service "microservicio-db" {
#     policy = "write"
#   }
#   service "mongo" {
#     policy = "read"
#   }
#   node_prefix "" {
#     policy = "read"
#   }
#   key_prefix "config/microservicio-db/" {
#     policy = "read"
#   }
#   key_prefix "config/shared/" {
#     policy = "read"
#   }
#   session_prefix "" {
#     policy = "write"
#   }

# ========================================================================
# Policy: traefik-policy (for Traefik Consul Catalog provider)
# ========================================================================
# Name: "traefik-policy"
# Description: "Policy for Traefik edge gateway"
# Rules:
#   service_prefix "" {
#     policy = "read"   # discover all services for routing
#   }
#   node_prefix "" {
#     policy = "read"
#   }
#   key_prefix "traefik/" {
#     policy = "read"   # dynamic config from KV
#   }

# ========================================================================
# Policy: operator-policy (for human operators / CI)
# ========================================================================
# Name: "operator-policy"
# Description: "Policy for operators (read-mostly, some write)"
# Rules:
#   service_prefix "" {
#     policy = "read"
#   }
#   node_prefix "" {
#     policy = "read"
#   }
#   key_prefix "" {
#     policy = "read"
#   }
#   key_prefix "config/" {
#     policy = "write"  # can update config
#   }
#   intention_prefix "" {
#     policy = "read"
#   }

# ---------------------------------------------------------------------------
# Intentions (Service-to-Service Authorization)
# Deny by default; explicit allow rules below.
# Apply via: consul intention create -allow <src> <dst>
# ---------------------------------------------------------------------------

# ========================================================================
# Intentions (apply after bootstrap via CLI or UI)
# ========================================================================
# consul intention create -allow monolitico microservicio-go
# consul intention create -allow monolitico microservicio-db
# consul intention create -allow microservicio-go redis
# consul intention create -allow microservicio-db mongo
#
# Default: deny (configured in server.hcl connect { default_policy = "deny" })

# ---------------------------------------------------------------------------
# Example: Create tokens after bootstrap (run once)
# ---------------------------------------------------------------------------
# export CONSUL_HTTP_TOKEN=dev-bootstrap-token
# export CONSUL_HTTP_ADDR=http://localhost:8500
#
# # Create policies
# consul acl policy create -name "monolitico-policy" -rules @monolitico-policy.hcl
# consul acl policy create -name "microservicio-go-policy" -rules @microservicio-go-policy.hcl
# consul acl policy create -name "microservicio-db-policy" -rules @microservicio-db-policy.hcl
# consul acl policy create -name "traefik-policy" -rules @traefik-policy.hcl
# consul acl policy create -name "operator-policy" -rules @operator-policy.hcl
#
# # Create tokens
# consul acl token create -description "monolitico" -policy-name "monolitico-policy"
# consul acl token create -description "microservicio-go" -policy-name "microservicio-go-policy"
# consul acl token create -description "microservicio-db" -policy-name "microservicio-db-policy"
# consul acl token create -description "traefik" -policy-name "traefik-policy"
# consul acl token create -description "operator" -policy-name "operator-policy"
#
# # Save token secrets to .env (gitignored)
# # CONSUL_TOKEN_MONOLITICO=...
# # CONSUL_TOKEN_GO=...
# # CONSUL_TOKEN_DB=...
# # CONSUL_TOKEN_TRAEFIK=...

# ---------------------------------------------------------------------------
# Policy Rule Files (for reference; apply via CLI)
# ---------------------------------------------------------------------------

# monolitico-policy.hcl:
# service "monolitico" { policy = "write" }
# service "microservicio-go" { policy = "read" }
# service "microservicio-db" { policy = "read" }
# node_prefix "" { policy = "read" }
# key_prefix "config/monolitico/" { policy = "read" }
# key_prefix "config/shared/" { policy = "read" }
# session_prefix "" { policy = "write" }

# microservicio-go-policy.hcl:
# service "microservicio-go" { policy = "write" }
# service "redis" { policy = "read" }
# node_prefix "" { policy = "read" }
# key_prefix "config/microservicio-go/" { policy = "read" }
# key_prefix "config/shared/" { policy = "read" }
# session_prefix "" { policy = "write" }

# microservicio-db-policy.hcl:
# service "microservicio-db" { policy = "write" }
# service "mongo" { policy = "read" }
# node_prefix "" { policy = "read" }
# key_prefix "config/microservicio-db/" { policy = "read" }
# key_prefix "config/shared/" { policy = "read" }
# session_prefix "" { policy = "write" }

# traefik-policy.hcl:
# service_prefix "" { policy = "read" }
# node_prefix "" { policy = "read" }
# key_prefix "traefik/" { policy = "read" }

# operator-policy.hcl:
# service_prefix "" { policy = "read" }
# node_prefix "" { policy = "read" }
# key_prefix "" { policy = "read" }
# key_prefix "config/" { policy = "write" }
# intention_prefix "" { policy = "read" }