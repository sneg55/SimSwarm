#!/bin/bash
# SimSwarm deployment script
# Usage: ssh root@server 'bash -s' < deploy.sh
#    or: ./deploy.sh  (when run on server)

set -euo pipefail

REPO_DIR="/opt/fishcloud"
APP_IMAGE="fishcloud-app"
HEALTH_URL="http://localhost:8080/api/health"
HEALTH_RETRIES=20
HEALTH_INTERVAL=3

red()   { echo -e "\033[0;31m$*\033[0m"; }
green() { echo -e "\033[0;32m$*\033[0m"; }
blue()  { echo -e "\033[0;34m$*\033[0m"; }

blue "=== SimSwarm Deploy ==="

# ── Prerequisites ──────────────────────────────────────────────────────────────

if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi

if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning repo..."
    git clone https://github.com/sneg55/SimSwarm.git "$REPO_DIR"
    cd "$REPO_DIR"
    git submodule update --init --recursive
else
    cd "$REPO_DIR"
    git pull origin main
    git submodule update --recursive
fi

if [ ! -f .env ]; then
    red "ERROR: .env file not found. Copy .env.production to .env and fill in values."
    exit 1
fi

# ── Step 1: Build single image ────────────────────────────────────────────────

blue "[1/5] Building app image..."
docker compose build --no-cache app
echo "    Image: $APP_IMAGE"

# ── Step 2: Validate migrations ───────────────────────────────────────────────

blue "[2/5] Checking migrations..."
heads=$(docker compose run --rm --no-deps app alembic heads 2>/dev/null | grep -c "head" || true)
if [ "$heads" -gt 1 ]; then
    red "ERROR: Multiple alembic heads detected. Fix before deploying:"
    docker compose run --rm --no-deps app alembic heads
    exit 1
fi
green "    Single migration head — OK"

# ── Step 3: Run migrations ────────────────────────────────────────────────────

blue "[3/5] Running migrations..."
docker compose run --rm migrate
green "    Migrations applied"

# ── Step 4: Deploy services ───────────────────────────────────────────────────

blue "[4/5] Deploying services..."

# Graceful Celery shutdown (finish in-flight tasks, 120s timeout)
docker compose stop -t 120 celery 2>/dev/null || true

# Copy frontend assets into Caddy volume
docker compose rm -f frontend-init 2>/dev/null || true
docker compose run --rm frontend-init

# Start all services
docker compose up -d app celery redis db caddy

# ── Step 5: Health check ──────────────────────────────────────────────────────

blue "[5/5] Waiting for health check..."
healthy=false
for i in $(seq 1 $HEALTH_RETRIES); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        healthy=true
        break
    fi
    echo "    Attempt $i/$HEALTH_RETRIES — waiting ${HEALTH_INTERVAL}s..."
    sleep $HEALTH_INTERVAL
done

if [ "$healthy" = true ]; then
    green "    Health check passed"
else
    red "ERROR: App failed health check after $((HEALTH_RETRIES * HEALTH_INTERVAL))s"
    echo "Logs:"
    docker compose logs --tail=30 app
    exit 1
fi

# ── Cleanup ───────────────────────────────────────────────────────────────────

docker image prune -f > /dev/null 2>&1

echo ""
green "=== Deploy complete ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
