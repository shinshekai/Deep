#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STATE_DIR="$PROJECT_DIR/scripts/.bg-state"
NGINX_CONF="$STATE_DIR/nginx.conf"
HEALTH_ENDPOINT="/api/v1/system/health/ready"
HEALTH_TIMEOUT=120
HEALTH_INTERVAL=5
CONF_TEMPLATE="$SCRIPT_DIR/nginx-blue-green.conf"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

ensure_state_dir() {
    mkdir -p "$STATE_DIR"
    if [ ! -f "$STATE_DIR/active_color" ]; then
        echo "blue" > "$STATE_DIR/active_color"
    fi
}

get_active_color() {
    if [ -f "$STATE_DIR/active_color" ]; then
        cat "$STATE_DIR/active_color" | tr -d '[:space:]'
    else
        echo "blue"
    fi
}

get_inactive_color() {
    local active
    active=$(get_active_color)
    if [ "$active" = "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

generate_nginx_conf() {
    local color=$1
    local backend_upstream="${color}-backend:8001"
    local frontend_upstream="${color}-frontend:3782"

    cat > "$NGINX_CONF" <<CONF
worker_processes auto;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 50m;

    log_format main '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                    '\$status \$body_bytes_sent "\$http_referer" '
                    '"\$http_user_agent" upstream=\$upstream_addr';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    map \$http_upgrade \$connection_upgrade {
        default upgrade;
        '' close;
    }

    upstream backend {
        server ${backend_upstream};
    }

    upstream frontend {
        server ${frontend_upstream};
    }

    server {
        listen 80;
        server_name _;

        location /nginx-health {
            access_log off;
            return 200 '{"status":"ok","active_color":"${color}"}';
            add_header Content-Type application/json;
        }

        location /api/v1/ {
            proxy_pass http://backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \$connection_upgrade;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }

        location /ws/ {
            proxy_pass http://backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \$connection_upgrade;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }

        location / {
            proxy_pass http://frontend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \$connection_upgrade;
        }
    }
}
CONF

    log "Generated nginx config for $color environment"
}

wait_for_health() {
    local color=$1
    local service="${color}-backend"
    local elapsed=0

    log "Waiting for $service to become healthy..."

    while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
        if docker compose -f "$PROJECT_DIR/docker-compose.blue-green.yml" ps "$service" 2>/dev/null | grep -q "(healthy)"; then
            log "$service is healthy (${elapsed}s)"
            return 0
        fi

        sleep $HEALTH_INTERVAL
        elapsed=$((elapsed + HEALTH_INTERVAL))
        log "  Still waiting... (${elapsed}s/${HEALTH_TIMEOUT}s)"
    done

    log "ERROR: $service failed to become healthy within ${HEALTH_TIMEOUT}s"
    return 1
}

switch_traffic() {
    local target_color=$1

    generate_nginx_conf "$target_color"
    echo "$target_color" > "$STATE_DIR/active_color"

    if docker compose -f "$PROJECT_DIR/docker-compose.blue-green.yml" restart nginx 2>/dev/null; then
        log "Restarted nginx with $target_color config"
    else
        log "WARNING: Could not restart nginx, traffic may not switch"
    fi

    echo "$target_color" > "$STATE_DIR/last_switch"
    log "Traffic switched to $target_color"
}

deploy_color() {
    local target_color=$1
    log "Deploying to $target_color environment..."

    docker compose -f "$PROJECT_DIR/docker-compose.blue-green.yml" up -d --build --no-deps "${target_color}-backend" "${target_color}-frontend"

    if ! wait_for_health "$target_color"; then
        log "Deployment to $target_color failed health checks"
        return 1
    fi

    log "$target_color environment deployed successfully"
}

rollback() {
    local previous_color
    if [ -f "$STATE_DIR/last_switch" ]; then
        previous_color=$(cat "$STATE_DIR/last_switch")
    else
        previous_color=$(get_inactive_color)
    fi

    log "Rolling back to $previous_color..."
    switch_traffic "$previous_color"
    log "Rollback complete. Active environment: $previous_color"
}

status() {
    local active
    active=$(get_active_color)
    local inactive
    inactive=$(get_inactive_color)

    echo "=========================================="
    echo "Blue-Green Deployment Status"
    echo "=========================================="
    echo ""
    echo "Active environment:   $active"
    echo "Standby environment: $inactive"
    echo ""

    if [ -f "$STATE_DIR/last_switch" ]; then
        echo "Last switch:          $(cat "$STATE_DIR/last_switch") at $(stat -c '%y' "$STATE_DIR/last_switch" 2>/dev/null || stat -f '%Sm' "$STATE_DIR/last_switch" 2>/dev/null || echo 'unknown')"
    fi
    echo ""

    echo "Container status:"
    docker compose -f "$PROJECT_DIR/docker-compose.blue-green.yml" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    echo ""
}

usage() {
    cat <<EOF
Usage: $(basename "$0") <command>

Commands:
    deploy      Deploy to inactive environment and switch traffic
    rollback    Switch back to previous environment
    status      Show current deployment status
    switch <color>   Manually switch traffic (blue|green)
    promote     Deploy to inactive and promote it to active

Examples:
    $(basename "$0") deploy
    $(basename "$0") rollback
    $(basename "$0") status
    $(basename "$0") switch green
EOF
}

main() {
    ensure_state_dir

    local cmd=${1:-help}
    shift || true

    case "$cmd" in
        deploy)
            local target
            target=$(get_inactive_color)
            log "Deploying to $target (currently active: $(get_active_color))"
            deploy_color "$target"
            switch_traffic "$target"
            log "Deployment complete. Active environment: $target"
            ;;
        rollback)
            rollback
            ;;
        status)
            status
            ;;
        switch)
            local color=${1:-}
            if [ -z "$color" ] || { [ "$color" != "blue" ] && [ "$color" != "green" ]; }; then
                log "ERROR: switch requires 'blue' or 'green'"
                usage
                exit 1
            fi
            switch_traffic "$color"
            log "Manual switch to $color complete"
            ;;
        promote)
            local target
            target=$(get_inactive_color)
            log "Promoting $target to active..."
            deploy_color "$target"
            switch_traffic "$target"
            log "Promotion complete. Active environment: $target"
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log "ERROR: Unknown command '$cmd'"
            usage
            exit 1
            ;;
    esac
}

main "$@"
