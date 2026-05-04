# Deployment Guide

Complete guide for deploying UDIP in production or development environments.

## Prerequisites

| Component | Minimum | Recommended |
|-----------|--------|-------------|
| **OS** | Windows 10/11, Linux (Ubuntu 20.04+), macOS 12+ | Linux (Ubuntu 22.04 LTS) |
| **Python** | 3.10+ | 3.12+ |
| **Node.js** | 18+ | 20+ |
| **GPU** | 6GB VRAM (Qwen3-1.7B) | 12GB+ VRAM (Qwen3-14B) |
| **RAM** | 16GB | 32GB |
| **Storage** | 10GB free | 50GB free SSD |
| **LM Studio** | v0.3.5+ | Latest version |

---

## Option 1: Docker Compose (Recommended)

### Quick Start

```bash
git clone https://github.com/shinshekai/Deep.git
cd Deep
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required
LLM_MODEL=Qwen3-4B-Q4_K_M
LLM_API_KEY=lm-studio
LLM_HOST=http://host.docker.internal:1234

EMBEDDING_MODEL=Snowflake-Arctic-Embed-M
EMBEDDING_API_KEY=lm-studio
EMBEDDING_HOST=http://host.docker.internal:1234

# Optional
BACKEND_PORT=8001
FRONTEND_PORT=3782
TURBOQUANT_ENABLED=true
```

Start services:

```bash
docker-compose up --build -d
```

Check status:

```bash
curl http://localhost:8001/api/v1/health
```

Access:
- **Frontend**: http://localhost:3782
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

### Docker Compose Architecture

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8001:8001"
    environment:
      - LLM_HOST=${LLM_HOST}
      - EMBEDDING_HOST=${EMBEDDING_HOST}
    volumes:
      - ./data:/app/data
    depends_on:
      - lm-studio

  frontend:
    build: ./frontend
    ports:
      - "3782:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8001

  lm-studio:
    image: lmstudio/lm-studio:latest
    ports:
      - "1234:1234"
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
```

---

## Option 2: Manual Deployment

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# or (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

Configure environment:

```bash
cp .env.example .env
# Edit .env with your settings
```

Run the backend:

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Development
npm run dev -- -p 3782

# Production build
npm run build
npm run start -- -p 3782
```

### LM Studio Setup

1. Download and install [LM Studio](https://lmstudio.ai)
2. Download a GGUF model (e.g., Qwen3-4B-Q4_K_M)
3. Start the server:
   - Open LM Studio → "Local Server" tab
   - Select your model
   - Click "Start Server" (port 1234)
4. Verify: `curl http://localhost:1234/v1/models`

---

## Linux systemd Services

### Backend Service

Create `/etc/systemd/system/udip-backend.service`:

```ini
[Unit]
Description=UDIP Backend
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Deep/backend
Environment="PATH=/path/to/Deep/backend/.venv/bin"
ExecStart=/path/to/Deep/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable udip-backend
sudo systemctl start udip-backend
sudo systemctl status udip-backend
```

### Frontend Service

Create `/etc/systemd/system/udip-frontend.service`:

```ini
[Unit]
Description=UDIP Frontend
After=udip-backend.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Deep/frontend
ExecStart=/usr/bin/npm run start -- -p 3782
Restart=always
RestartSec=10
Environment="NODE_ENV=production"

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable udip-frontend
sudo systemctl start udip-frontend
sudo systemctl status udip-frontend
```

---

## GPU Requirements by Model Tier

| Model | VRAM Required | Use Case |
|-------|-----------|----------|
| Qwen3-0.6B | 0.5 GB | Embedding, retrieval scoring |
| Qwen3-1.7B | 1.2 GB | T1 default |
| Qwen3-4B | 2.5 GB | T2 balanced |
| Qwen3-8B | 5.5 GB | T2 high-quality |
| Qwen3-14B | 8.5 GB | T3 precision |
| Qwen3-30B-A3B | 18 GB | T3 MoE (best quality) |

**TurboQuant note:** When enabled, KV cache quantization reduces VRAM usage by ~59% with only 0.86% perplexity loss.

---

## Verification Checklist

After deployment, verify:

- [ ] `curl http://localhost:8001/api/v1/health` returns `{"status": "healthy"}`
- [ ] `curl http://localhost:8001/api/v1/models` returns model list
- [ ] Open http://localhost:3782 in browser
- [ ] Upload a test document via the UI
- [ ] Perform a test query
- [ ] Check GPU VRAM usage: `nvidia-smi`

---

## Troubleshooting

### Backend can't connect to LM Studio
- Verify LM Studio is running: `curl http://localhost:1234/v1/models`
- Check `LLM_HOST` in `.env` matches LM Studio's actual address
- Windows: LM Studio may bind to `127.0.0.1` not `0.0.0.0`

### GPU not detected
```bash
nvidia-smi  # Check driver
pip install pynvml  # Reinstall Python bindings
```

### Out of VRAM
- Use smaller models (Qwen3-1.7B instead of 14B)
- Enable TurboQuant: `TURBOQUANT_ENABLED=true`
- Reduce T2/T3 TTL values in settings

### Port already in use
```bash
# Check what's using the port
netstat -ano | findstr :8001  # Windows
lsof -i :8001  # Linux/macOS
```

---

## Security Considerations (Production)

- Set `LLM_API_KEY` to a strong secret (not "lm-studio")
- Restrict `ALLOWED_ORIGINS` to your domain only
- Use HTTPS (reverse proxy with nginx/Caddy)
- Don't expose LM Studio port (1234) to the internet
- Regular security updates: `pip install -U fastapi uvicorn`

---

## Performance Tuning

| Setting | Default | Recommendation |
|---------|--------|-------------|
| `T2_TTL_SECONDS` | 600 | Reduce to 300 if memory-constrained |
| `T3_TTL_SECONDS` | 300 | Reduce to 180 if memory-constrained |
| `VRAM_SAFETY_MARGIN_PCT` | 15 | Increase to 20 for stability |
| `PAGEINDEX_MAX_PAGES_PER_NODE` | 10 | Reduce to 5 for faster indexing |
