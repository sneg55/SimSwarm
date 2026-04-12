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
MINIO_PULL_OK=0
if [ -d "$MODEL_CACHE/snapshots" ] && [ -n "$(find "$MODEL_CACHE/snapshots" -name 'config.json' 2>/dev/null | head -1)" ]; then
    echo "[start.sh] Model cache present at $MODEL_CACHE"
    MINIO_PULL_OK=1
elif [ -z "${MINIO_ENDPOINT}" ] || [ -z "${MINIO_ACCESS_KEY}" ] || [ -z "${MINIO_SECRET_KEY}" ]; then
    echo "[start.sh] MinIO env vars missing, falling back to HuggingFace download"
else
    echo "[start.sh] Pulling ${MODEL_ID} from MinIO to ${DOWNLOAD_DIR}..."
    mkdir -p "$DOWNLOAD_DIR"
    MINIO_SCHEME="http"
    [ "${MINIO_SECURE}" = "true" ] && MINIO_SCHEME="https"
    START=$(date +%s)
    # MinIO has the HF cache tree rooted under models/hf-cache/ —
    # s5cmd's recursive cp preserves the models--Qwen--Qwen3-14B/snapshots/{hash}/
    # layout that vLLM/huggingface_hub expect. The trailing /* pulls everything
    # under hf-cache/ directly into DOWNLOAD_DIR (i.e. HF_HOME).
    AWS_ACCESS_KEY_ID="${MINIO_ACCESS_KEY}" \
    AWS_SECRET_ACCESS_KEY="${MINIO_SECRET_KEY}" \
    s5cmd --endpoint-url "${MINIO_SCHEME}://${MINIO_ENDPOINT}" \
          cp -c 16 "s3://${MINIO_BUCKET:-simswarm}/models/hf-cache/*" \
          "${DOWNLOAD_DIR}/"
    RC=$?
    ELAPSED=$(($(date +%s) - START))
    if [ $RC -eq 0 ]; then
        echo "[start.sh] MinIO pull complete in ${ELAPSED}s"
        MINIO_PULL_OK=1
    else
        echo "[start.sh] MinIO pull failed (rc=$RC) after ${ELAPSED}s, falling back to HuggingFace"
    fi
fi

# When our MinIO cache is populated, point vLLM at the snapshot directory
# directly. This bypasses huggingface_hub's ETag validation (which would
# re-download the 29GB from HF on every start — see vLLM weight_utils.py:281
# "Time spent downloading weights...") AND avoids transformers' strict
# offline-mode lookup that requires a full symlink-to-blobs layout we don't
# replicate from MinIO. Serving name stays "Qwen/Qwen3-14B" so clients and
# tokenizer config are unchanged.
MODEL_ARG="${MODEL_ID:-Qwen/Qwen3-14B}"
SERVED_NAME_ARG=""
if [ "$MINIO_PULL_OK" = "1" ]; then
    SNAPSHOT_DIR=$(find "$MODEL_CACHE/snapshots" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -1)
    if [ -n "$SNAPSHOT_DIR" ] && [ -f "$SNAPSHOT_DIR/config.json" ]; then
        MODEL_ARG="$SNAPSHOT_DIR"
        SERVED_NAME_ARG="--served-model-name ${MODEL_ID:-Qwen/Qwen3-14B}"
        echo "[start.sh] Loading from local snapshot: $SNAPSHOT_DIR"
    else
        echo "[start.sh] WARN: cache present but no snapshot/config.json found, falling back to HF repo id"
    fi
fi

# Start vLLM in background, log to file
python3 -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 --port 8000 \
    --model "$MODEL_ARG" \
    $SERVED_NAME_ARG \
    --download-dir ${DOWNLOAD_DIR} \
    ${VLLM_ARGS:---max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes} \
    > /tmp/vllm.log 2>&1 &

VLLM_PID=$!
echo "[start.sh] vLLM started with PID $VLLM_PID"

# Start worker API in foreground
echo "[start.sh] Starting worker API on port 5000..."
python3 /app/worker_api.py
