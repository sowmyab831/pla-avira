#!/usr/bin/env bash
# Rebuild the AVIRA frontend image and roll the K8s deployment.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${NS:-pla}"
TS="$(date +%Y%m%d-%H%M)"
SHA="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo nogit)"
TAG="${TS}-${SHA}"
IMAGE_NAME="${IMAGE_NAME:-pla-frontend}"
IMAGE="${IMAGE_NAME}:${TAG}"

echo "[avira] building $IMAGE ..."
docker build \
  -t "$IMAGE" \
  -t "${IMAGE_NAME}:latest" \
  -f "${ROOT_DIR}/frontend/Dockerfile" \
  "${ROOT_DIR}/frontend"

echo "[avira] setting image on deployment/frontend in namespace $NS ..."
kubectl -n "$NS" set image deploy/frontend "frontend=${IMAGE}"
kubectl -n "$NS" rollout status deploy/frontend --timeout=180s

echo "[avira] frontend redeploy complete. Image: $IMAGE"
echo "Open: http://localhost:30001/#forecast"
