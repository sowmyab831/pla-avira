#!/usr/bin/env bash
# Rebuild the AVIRA backend image (with trained XGBoost models baked in) and
# roll the K8s deployment so the cluster picks up the new code.
#
# Steps:
#   1. Stage trained XGBoost models from meridian/research/models/ into
#      backend/_models_staged/ so Dockerfile can COPY them.
#   2. Build a uniquely-tagged image (pla-backend:YYYYmmdd-HHMM-<git>).
#   3. Tag it as :latest so the existing manifest keeps working.
#   4. kubectl set image + rollout restart + rollout status.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${NS:-pla}"
TS="$(date +%Y%m%d-%H%M)"
SHA="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo nogit)"
TAG="${TS}-${SHA}"
IMAGE_NAME="${IMAGE_NAME:-pla-backend}"
IMAGE="${IMAGE_NAME}:${TAG}"

MODELS_SRC="${ROOT_DIR}/meridian/research/models"
MODELS_DST="${ROOT_DIR}/backend/_models_staged"

echo "[avira] staging trained models from $MODELS_SRC ..."
rm -rf "$MODELS_DST"
mkdir -p "$MODELS_DST"
if [ -d "$MODELS_SRC" ] && compgen -G "$MODELS_SRC/*.pkl" > /dev/null; then
  cp "$MODELS_SRC"/*.pkl "$MODELS_DST/" 2>/dev/null || true
  [ -f "$MODELS_SRC/training_report.json" ] && cp "$MODELS_SRC/training_report.json" "$MODELS_DST/"
  echo "[avira] staged $(ls "$MODELS_DST" | wc -l) model artifacts."
else
  echo "[avira] no trained models found — building without ML tilt."
  touch "$MODELS_DST/.placeholder"
fi

echo "[avira] building $IMAGE ..."
docker build \
  -t "$IMAGE" \
  -t "${IMAGE_NAME}:latest" \
  -f "${ROOT_DIR}/backend/Dockerfile" \
  "${ROOT_DIR}/backend"

# OrbStack/k3s share the host Docker daemon — image is already accessible.
# For remote registries, push here:
#   docker push "$IMAGE"

echo "[avira] setting image on deployment/backend in namespace $NS ..."
kubectl -n "$NS" set image deploy/backend "backend=${IMAGE}"
kubectl -n "$NS" rollout status deploy/backend --timeout=180s

echo "[avira] cleaning staged models ..."
rm -rf "$MODELS_DST"

echo "[avira] redeploy complete. Image: $IMAGE"
echo "Smoke test (from host):"
echo "  curl -s http://localhost:30000/api/market-intel/ai-boom | jq .ai_boom_score"
echo "  curl -s http://localhost:30000/api/forecast/long-term/NVDA | jq .forecasts.\\\"30d\\\""
echo "  curl -s http://localhost:30000/api/forecast/models-used | jq .llms"
