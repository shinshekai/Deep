#!/usr/bin/env python3
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
STATE_DIR = SCRIPT_DIR / ".bg-state"
ACTIVE_COLOR_FILE = STATE_DIR / "active_color"
LAST_SWITCH_FILE = STATE_DIR / "last_switch"
NGINX_CONF_FILE = STATE_DIR / "nginx.conf"
COMPOSE_FILE = PROJECT_DIR / "docker-compose.blue-green.yml"
HEALTH_RETRIES = 3
HEALTH_INTERVAL = 5

NGINX_TEMPLATE = """\
worker_processes auto;
pid /tmp/nginx.pid;
events {{
    worker_connections 1024;
}}
http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 50m;
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" upstream=$upstream_addr';
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;
    map $http_upgrade $connection_upgrade {{
        default upgrade;
        '' close;
    }}
    upstream backend {{
        server {color}-backend:8001;
    }}
    upstream frontend {{
        server {color}-frontend:3782;
    }}
    server {{
        listen 80;
        server_name _;
        location /nginx-health {{
            access_log off;
            return 200 '{{"status":"ok","active_color":"{color}"}}';
            add_header Content-Type application/json;
        }}
        location /api/v1/ {{
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }}
        location /ws/ {{
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }}
        location / {{
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
        }}
    }}
}}
"""

def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")
def run(cmd, check=True):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        log(f"Command failed: {' '.join(cmd)}")
        if result.stderr:
            log(result.stderr.strip())
        sys.exit(1)
    return result
def docker_compose(*args, check=True):
    return run(["docker", "compose", "-f", str(COMPOSE_FILE), *args], check=check)
def ensure_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not ACTIVE_COLOR_FILE.exists():
        ACTIVE_COLOR_FILE.write_text("blue")
def get_active_color():
    return ACTIVE_COLOR_FILE.read_text().strip() if ACTIVE_COLOR_FILE.exists() else "blue"
def get_inactive_color():
    return "green" if get_active_color() == "blue" else "blue"
def wait_for_health(color):
    service = f"{color}-backend"
    log(f"Waiting for {service} to become healthy...")
    for attempt in range(1, HEALTH_RETRIES + 1):
        result = docker_compose("ps", service, check=False)
        if "(healthy)" in result.stdout:
            log(f"{service} is healthy (attempt {attempt}/{HEALTH_RETRIES})")
            return True
        if attempt < HEALTH_RETRIES:
            log(f"  Attempt {attempt}/{HEALTH_RETRIES} failed, retrying in {HEALTH_INTERVAL}s...")
            time.sleep(HEALTH_INTERVAL)
    log(f"ERROR: {service} failed to become healthy after {HEALTH_RETRIES} attempts")
    return False
def switch_traffic(target_color):
    NGINX_CONF_FILE.write_text(NGINX_TEMPLATE.format(color=target_color))
    log(f"Generated nginx config for {target_color} environment")
    ACTIVE_COLOR_FILE.write_text(target_color)
    result = docker_compose("restart", "nginx", check=False)
    if result.returncode != 0:
        log("WARNING: Could not restart nginx, traffic may not switch")
    else:
        log(f"Restarted nginx with {target_color} config")
    LAST_SWITCH_FILE.write_text(target_color)
    log(f"Traffic switched to {target_color}")
def deploy_color(color):
    log(f"Deploying to {color} environment...")
    docker_compose("up", "-d", "--build", "--no-deps", f"{color}-backend", f"{color}-frontend")
    if not wait_for_health(color):
        log(f"Deployment to {color} failed health checks")
        return False
    log(f"{color} environment deployed successfully")
    return True
def deploy():
    target = get_inactive_color()
    active = get_active_color()
    log(f"Deploying to {target} (currently active: {active})")
    if not deploy_color(target):
        log("Deployment failed, rolling back to previous environment...")
        switch_traffic(active)
        log(f"Rollback complete. Active environment: {active}")
        sys.exit(1)
    switch_traffic(target)
    log(f"Deployment complete. Active environment: {target}")
def rollback():
    if LAST_SWITCH_FILE.exists():
        last = LAST_SWITCH_FILE.read_text().strip()
        previous_color = "green" if last == "blue" else "blue"
    else:
        previous_color = get_active_color()
    log(f"Rolling back to {previous_color}...")
    switch_traffic(previous_color)
    log(f"Rollback complete. Active environment: {previous_color}")
def status():
    active = get_active_color()
    inactive = get_inactive_color()
    print("==========================================")
    print("Blue-Green Deployment Status")
    print("==========================================\n")
    print(f"Active environment:   {active}")
    print(f"Standby environment:  {inactive}\n")
    if LAST_SWITCH_FILE.exists():
        print(f"Last switch:          {LAST_SWITCH_FILE.read_text().strip()}\n")
    print("Container status:")
    docker_compose("ps", "--format", "table {{.Name}}\t{{.Status}}\t{{.Ports}}", check=False)
    print()
def main():
    ensure_state()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "deploy":
        deploy()
    elif cmd == "rollback":
        rollback()
    elif cmd == "status":
        status()
    elif cmd in ("help", "--help", "-h"):
        print("Usage: orchestrate.py [deploy|rollback|status]")
    else:
        log(f"ERROR: Unknown command '{cmd}'")
        print("Usage: orchestrate.py [deploy|rollback|status]")
        sys.exit(1)

if __name__ == "__main__":
    main()
