#!/bin/bash
# Setup Consul Connect Intentions for Service Mesh
# Run this after all services are registered with Consul

set -e

CONSUL_ADDR="${CONSUL_HTTP_ADDR:-http://localhost:8500}"
CONSUL_TOKEN="${CONSUL_HTTP_TOKEN:-dev-bootstrap-token}"

echo "Setting up Consul Connect intentions..."
echo "Consul address: $CONSUL_ADDR"

# Function to create/check intention
create_intention() {
    local src=$1
    local dst=$2
    local action=${3:-allow}
    
    echo "Creating intention: $src -> $dst ($action)"
    
    # Check if intention exists
    if consul intention check -src "$src" -dst "$dst" -http-addr "$CONSUL_ADDR" -token "$CONSUL_TOKEN" 2>/dev/null | grep -q "$action"; then
        echo "  Intention already exists: $src -> $dst ($action)"
    else
        consul intention create -src "$src" -dst "$dst" -action "$action" -http-addr "$CONSUL_ADDR" -token "$CONSUL_TOKEN"
        echo "  Created: $src -> $dst ($action)"
    fi
}

# Wait for Consul to be ready
echo "Waiting for Consul to be ready..."
until curl -sf "$CONSUL_ADDR/v1/status/leader" -H "X-Consul-Token: $CONSUL_TOKEN" >/dev/null 2>&1; do
    sleep 2
done
echo "Consul is ready!"

# Create intentions (deny by default, so we explicitly allow)
# Service-to-service intentions for mTLS
# monolitico -> microservicio-go (for PDF extraction)
create_intention "monolitico" "microservicio-go" "allow"

# monolitico -> microservicio-db (for document persistence)
create_intention "monolitico" "microservicio-db" "allow"

# monolitico -> microservicio-resume (for summary generation)
create_intention "monolitico" "microservicio-resume" "allow"

# microservicio-resume -> microservicio-db (for summary persistence)
create_intention "microservicio-resume" "microservicio-db" "allow"

# microservicio-go -> redis (for cache) - if redis has sidecar
# create_intention "microservicio-go" "redis" "allow"

# microservicio-db -> mongo (for database) - if mongo has sidecar
# create_intention "microservicio-db" "mongo" "allow"

# Sidecar-to-sidecar intentions (internal, for Connect proxy authorization)
# These are automatically created when sidecars are registered with intentions above
# But we can also explicitly create them for clarity:
# create_intention "monolitico-sidecar" "microservicio-go-sidecar" "allow"
# create_intention "monolitico-sidecar" "microservicio-db-sidecar" "allow"
# create_intention "monolitico-sidecar" "microservicio-resume-sidecar" "allow"

echo ""
echo "Listing all intentions:"
consul intention list -http-addr "$CONSUL_ADDR" -token "$CONSUL_TOKEN"

echo ""
echo "Intentions setup complete!"
echo ""
echo "Note: Intentions for redis and mongo are commented out since they don't have sidecars."
echo "If you deploy redis/mongo with Consul Connect sidecars, uncomment those lines."