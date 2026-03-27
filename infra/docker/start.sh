#!/bin/bash
# Start vLLM in background
python3 -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 --port 8000 \
    --model ${MODEL_ID:-Qwen/Qwen2.5-32B-Instruct-AWQ} \
    ${VLLM_ARGS:---quantization awq --max-model-len 32768} &

# Start worker API in foreground
python3 /app/worker_api.py
