#!/usr/bin/env bash
# install.sh — One-command DEEP launcher for Linux/macOS
# Usage: bash install.sh
# Starts DEEP backend + frontend, opens browser to localhost:3782

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

step() { echo -e "${CYAN}[DEEP]${NC} $1"; }
ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "  ${RED}[ERR]${NC} $1"; }

DEEP_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3782}"
LM_STUDIO_HOST="${LM_STUDIO_HOST:-http://localhost:1234}"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   DEEP — Document Intelligence      ║${NC}"
echo -e "${CYAN}║   One-Command Installer             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── OS Detection ──
step "Detecting operating system..."
case "$(uname -s)" in
    Linux*)  OS="linux";;
    Darwin*) OS="macos";;
    *)       OS="unknown";;
esac
ok "OS: $OS"

# ── Prerequisites ──
step "Checking prerequisites..."

MISSING=0

if command -v docker &>/dev/null; then
    ok "Docker found: $(docker --version)"
    USE_DOCKER=true
elif command -v python3 &>/dev/null && command -v node &>/dev/null; then
    ok "Python: $(python3 --version) | Node: $(node --version)"
    USE_DOCKER=false
else
    err "Neither Docker nor Python+Node found"
    MISSING=1
fi

if [ "$MISSING" -eq 1 ]; then
    err "Please install Docker (recommended) or Python 3.12+ with Node 20+"
    exit 1
fi

# ── LM Studio check ──
step "Checking LM Studio..."
if curl -sf "${LM_STUDIO_HOST}/v1/models" >/dev/null 2>&1; then
    ok "LM Studio reachable at $LM_STUDIO_HOST"
else
    warn "LM Studio not reachable at $LM_STUDIO_HOST"
    warn "Install LM Studio from https://lmstudio.ai for local AI"
    warn "Or set LM_STUDIO_HOST env var to your endpoint"
fi

# ── Generate .env ──
step "Generating .env configuration..."
if [ ! -f "$DEEP_DIR/.env" ]; then
    cat > "$DEEP_DIR/.env" <<EOF
WS_AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -hex 32)
LLM_HOST=${LM_STUDIO_HOST}
BACKEND_PORT=${BACKEND_PORT}
FRONTEND_PORT=${FRONTEND_PORT}
EOF
    ok ".env generated with random auth token"
else
    ok ".env already exists — keeping existing config"
fi

# ── Start services ──
if [ "$USE_DOCKER" = true ]; then
    step "Starting DEEP with Docker Compose..."
    cd "$DEEP_DIR"
    docker compose up -d --build 2>/dev/null || docker-compose up -d --build
    ok "Docker containers started"
    sleep 5
else
    step "Starting backend server..."
    cd "$DEEP_DIR/backend"
    python3 -m uv run uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
    BACKEND_PID=$!
    ok "Backend PID: $BACKEND_PID"

    step "Starting frontend dev server..."
    cd "$DEEP_DIR/frontend"
    npm run dev -- -p "$FRONTEND_PORT" &
    FRONTEND_PID=$!
    ok "Frontend PID: $FRONTEND_PID"
fi

# ── Health check ──
step "Waiting for backend..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${BACKEND_PORT}/api/v1/health" >/dev/null 2>&1; then
        ok "Backend is ready!"
        break
    fi
    sleep 2
done

# ── Print info ──
TOKEN=$(grep WS_AUTH_TOKEN "$DEEP_DIR/.env" 2>/dev/null | cut -d= -f2 || echo "check .env file")
echo ""
echo -e "${GREEN}DEEP is running!${NC}"
echo -e "  Frontend: ${CYAN}http://localhost:${FRONTEND_PORT}${NC}"
echo -e "  Backend:  ${CYAN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo -e "  Auth token: ${YELLOW}${TOKEN}${NC}"
echo ""

# ── Open browser ──
if command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:${FRONTEND_PORT}" &>/dev/null &
elif command -v open &>/dev/null; then
    open "http://localhost:${FRONTEND_PORT}"
fi

echo -e "Press ${YELLOW}Ctrl+C${NC} to stop all services"
if [ "$USE_DOCKER" != true ]; then
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
    wait
fi
