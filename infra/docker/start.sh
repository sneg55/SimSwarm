#!/bin/bash
# Don't use set -e — vLLM might fail and we still want worker_api to serve logs

echo "[start.sh] MODEL_ID=${MODEL_ID:-not set}"
echo "[start.sh] VLLM_ARGS=${VLLM_ARGS:-not set}"
echo "[start.sh] Starting vLLM server..."

# Use network volume for model downloads (avoid filling container disk)
DOWNLOAD_DIR="${HF_HOME:-/models/huggingface}"
echo "[start.sh] DOWNLOAD_DIR=${DOWNLOAD_DIR}"

# Clear stale model cache if config.json is missing model_type
# (network volumes may have corrupt downloads from older transformers)
MODEL_CACHE="${DOWNLOAD_DIR}/models--${MODEL_ID//\//-}"
if [ -d "$MODEL_CACHE" ]; then
    CONFIG=$(find "$MODEL_CACHE" -name "config.json" -path "*/snapshots/*" | head -1)
    if [ -n "$CONFIG" ] && ! python3 -c "import json; c=json.load(open('$CONFIG')); assert 'model_type' in c" 2>/dev/null; then
        echo "[start.sh] Stale model cache detected (missing model_type), clearing..."
        rm -rf "$MODEL_CACHE"
    fi
fi

# Start vLLM in background, log to file
python3 -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 --port 8000 \
    --model ${MODEL_ID:-Qwen/Qwen3-14B} \
    --download-dir ${DOWNLOAD_DIR} \
    ${VLLM_ARGS:---max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes} \
    > /tmp/vllm.log 2>&1 &

VLLM_PID=$!
echo "[start.sh] vLLM started with PID $VLLM_PID"

# Start worker API in foreground
echo "[start.sh] Starting worker API on port 5000..."
python3 /app/worker_api.py
