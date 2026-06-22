#!/usr/bin/env bash
# scripts/build-offline-package.sh — Build self-contained offline distribution
# Usage: bash scripts/build-offline-package.sh [version]
# Creates: dist/deep-offline-{version}.tar.gz containing Docker images + compose

set -euo pipefail

VERSION="${1:-$(date +%Y.%m.%d)}"
DIST_DIR="dist/deep-offline-${VERSION}"
OUTPUT_FILE="deep-offline-${VERSION}.tar.gz"

echo "=== Building DEEP Offline Package v${VERSION} ==="
mkdir -p "${DIST_DIR}"

# ── Build Docker images ──
echo "Building backend image..."
docker compose build backend 2>/dev/null || docker-compose build backend

echo "Building frontend image..."
docker compose build frontend 2>/dev/null || docker-compose build frontend

# ── Save images as .tar ──
echo "Saving Docker images..."
docker save -o "${DIST_DIR}/deep-backend.tar" deep-backend:latest 2>/dev/null || \
  docker save -o "${DIST_DIR}/deep-backend.tar" $(docker compose images -q backend 2>/dev/null || echo "")

# ── Copy compose + env + scripts ──
echo "Copying deployment files..."
cp docker-compose.release.yml "${DIST_DIR}/docker-compose.yml"
echo "WS_AUTH_TOKEN=change-me-on-first-start" > "${DIST_DIR}/.env.example"
echo "BACKEND_PORT=8001" >> "${DIST_DIR}/.env.example"
echo "FRONTEND_PORT=3782" >> "${DIST_DIR}/.env.example"
echo "LLM_HOST=http://localhost:1234" >> "${DIST_DIR}/.env.example"

# ── Generate offline install script ──
cat > "${DIST_DIR}/install-offline.sh" <<'SCRIPT'
#!/usr/bin/env bash
set -e
echo "=== DEEP Offline Installer ==="
echo "Loading Docker images..."
docker load -i deep-backend.tar
echo "Starting DEEP..."
cp .env.example .env
docker compose up -d
echo ""
echo "DEEP is running at http://localhost:3782"
echo "Edit .env to configure your auth token and LLM endpoint"
SCRIPT
chmod +x "${DIST_DIR}/install-offline.sh"

cat > "${DIST_DIR}/install-offline.ps1" <<'PS1'
Write-Host "=== DEEP Offline Installer ==="
Write-Host "Loading Docker images..."
docker load -i deep-backend.tar
Write-Host "Starting DEEP..."
Copy-Item .env.example .env
docker compose up -d
Write-Host ""
Write-Host "DEEP is running at http://localhost:3782"
Write-Host "Edit .env to configure your auth token and LLM endpoint"
PS1

# ── Create README ──
cat > "${DIST_DIR}/README-OFFLINE.txt" <<'README'
DEEP Offline Installation Package
==================================

Requirements:
- Docker Engine 24+ (no internet needed after image load)
- LM Studio or Ollama running locally with models downloaded

Installation:
  Linux/Mac:  bash install-offline.sh
  Windows:    .\install-offline.ps1

Configuration:
  Edit .env to set:
    WS_AUTH_TOKEN  — change the default token
    LLM_HOST       — your LM Studio/Ollama endpoint (default: http://localhost:1234)

Access:
  Frontend: http://localhost:3782
  Backend:  http://localhost:8001/docs

Troubleshooting:
  If Docker images fail to load, try: docker load -i deep-backend.tar
  If port conflicts, edit BACKEND_PORT and FRONTEND_PORT in .env
README

# ── Package ──
echo "Creating archive..."
cd dist
tar -czf "${OUTPUT_FILE}" "deep-offline-${VERSION}"
rm -rf "deep-offline-${VERSION}"

echo ""
echo "=== Package ready: dist/${OUTPUT_FILE} ==="
ls -lh "dist/${OUTPUT_FILE}"
