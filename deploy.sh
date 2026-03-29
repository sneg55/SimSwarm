#!/bin/bash
# SimSwarm deployment script for Hetzner
# Usage: ssh root@your-server 'bash -s' < deploy.sh

set -euo pipefail

echo "=== SimSwarm Deploy ==="

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi

# Clone repo (first deploy) or pull (update)
REPO_DIR="/opt/fishcloud"
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning repo..."
    git clone https://github.com/sneg55/SimSwarm.git "$REPO_DIR"
    cd "$REPO_DIR"
    git submodule update --init --recursive
else
    echo "Pulling latest..."
    cd "$REPO_DIR"
    git pull
    git submodule update --recursive
fi

# Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.production to .env and fill in values."
    echo "  cp .env.production .env && nano .env"
    exit 1
fi

# Build and deploy
echo "Building and starting services..."
docker compose build
docker compose run --rm migrate
docker compose run --rm frontend-init
docker compose up -d app celery redis db caddy

echo ""
echo "=== Deploy complete ==="
echo "Services: $(docker compose ps --format '{{.Name}}: {{.Status}}' | tr '\n' ', ')"
echo "Logs: docker compose logs -f"
