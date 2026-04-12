#!/bin/bash
# Don't use set -e — vLLM might fail and we still want worker_api to serve logs

echo "[start.sh] MODEL_ID=${MODEL_ID:-not set}"
echo "[start.sh] VLLM_ARGS=${VLLM_ARGS:-not set}"
echo "[start.sh] Starting vLLM server..."

DOWNLOAD_DIR="${HF_HOME:-/models/huggingface}"
echo "[start.sh] DOWNLOAD_DIR=${DOWNLOAD_DIR}"

# Pull Qwen3-14B weights from our MinIO cache if not already present. MinIO
# holds a one-time upload of the model (see infra/scripts/upload_model_to_minio.py);
# any pod in any DC can fetch it at ~500MB/s without hitting the HuggingFace
# CDN. This keeps pod startup ~5 min even with no volume cache.
MODEL_CACHE="${DOWNLOAD_DIR}/models--${MODEL_ID//\//--}"
if [ ! -d "$MODEL_CACHE/snapshots" ] || [ -z "$(find "$MODEL_CACHE/snapshots" -name 'config.json' 2>/dev/null | head -1)" ]; then
    if [ -z "${MINIO_ENDPOINT}" ] || [ -z "${MINIO_ACCESS_KEY}" ] || [ -z "${MINIO_SECRET_KEY}" ]; then
        echo "[start.sh] MinIO env vars missing, falling back to HuggingFace download"
    else
        echo "[start.sh] Pulling ${MODEL_ID} from MinIO to ${DOWNLOAD_DIR}..."
        mkdir -p "$DOWNLOAD_DIR"
        MINIO_SCHEME="http"
        [ "${MINIO_SECURE}" = "true" ] && MINIO_SCHEME="https"
        START=$(date +%s)
        AWS_ACCESS_KEY_ID="${MINIO_ACCESS_KEY}" \
        AWS_SECRET_ACCESS_KEY="${MINIO_SECRET_KEY}" \
        s5cmd --endpoint-url "${MINIO_SCHEME}://${MINIO_ENDPOINT}" \
              cp -c 16 "s3://${MINIO_BUCKET:-simswarm}/models/${MODEL_ID}/*" \
              "${MODEL_CACHE}/"
        RC=$?
        ELAPSED=$(($(date +%s) - START))
        if [ $RC -eq 0 ]; then
            echo "[start.sh] MinIO pull complete in ${ELAPSED}s"
        else
            echo "[start.sh] MinIO pull failed (rc=$RC) after ${ELAPSED}s, falling back to HuggingFace"
        fi
    fi
else
    echo "[start.sh] Model cache present at $MODEL_CACHE"
fi

# Start vLLM in background, log to file
python3 -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 --port 8000 \
    --model ${MODEL_ID:-Qwen/Qwen3-14B} \
    --download-dir ${DOWNLOAD_DIR} \
    ${VLLM_ARGS:---max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes} \
    > /tmp/vllm.log 2>&1 &

VLLM_PID=$!
echo "[start.sh] vLLM started with PID $VLLM_PID"

# Start worker API in foreground
echo "[start.sh] Starting worker API on port 5000..."
python3 /app/worker_api.py
