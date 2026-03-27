#!/bin/bash
set -e

echo "[start.sh] MODEL_ID=${MODEL_ID:-not set}"
echo "[start.sh] VLLM_ARGS=${VLLM_ARGS:-not set}"
echo "[start.sh] Starting vLLM server..."

# Start vLLM in background, log to file
python3 -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 --port 8000 \
    --model ${MODEL_ID:-Qwen/Qwen2.5-32B-Instruct-AWQ} \
    ${VLLM_ARGS:---quantization awq --max-model-len 32768} \
    > /tmp/vllm.log 2>&1 &

VLLM_PID=$!
echo "[start.sh] vLLM started with PID $VLLM_PID"

# Start worker API in foreground
echo "[start.sh] Starting worker API on port 5000..."
python3 /app/worker_api.py
