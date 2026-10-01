#!/usr/bin/env bash
# AVIRA Start Orchestrator
# Brings up: OrbStack -> K3s/K8s pods (pla namespace) -> Ollama -> Meridian bot -> Frontend
# Usage: ./scripts/avira-start.sh [--no-meridian] [--no-frontend]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/.avira-logs"
mkdir -p "${LOG_DIR}"

NO_MERIDIAN=0
NO_FRONTEND=0
for arg in "$@"; do
  case "$arg" in
    --no-meridian) NO_MERIDIAN=1 ;;
    --no-frontend) NO_FRONTEND=1 ;;
  esac
done

log()  { printf "\033[1;36m[avira]\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m[ ok ]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[err ]\033[0m %s\n" "$*"; }

# 1. OrbStack
if command -v orbctl >/dev/null 2>&1; then
  log "Starting OrbStack..."
  if orbctl status 2>/dev/null | grep -qi running; then
    ok "OrbStack already running"
  else
    orbctl start
    sleep 3
    ok "OrbStack started"
  fi
else
  warn "orbctl not found — skipping OrbStack step"
fi

# 2. Kubernetes pods (pla namespace)
if command -v kubectl >/dev/null 2>&1; then
  log "Ensuring K8s 'pla' namespace pods are up..."
  kubectl get ns pla >/dev/null 2>&1 || kubectl apply -f "${ROOT_DIR}/k8s/namespace.yaml"

  for d in postgres redis qdrant meili backend frontend; do
    if kubectl -n pla get deploy "$d" >/dev/null 2>&1; then
      kubectl -n pla scale deploy/"$d" --replicas=1 >/dev/null 2>&1 || true
    fi
  done
  for s in qdrant; do
    if kubectl -n pla get statefulset "$s" >/dev/null 2>&1; then
      kubectl -n pla scale statefulset/"$s" --replicas=1 >/dev/null 2>&1 || true
    fi
  done

  log "Waiting for backend + frontend rollout (60s timeout)..."
  kubectl -n pla rollout status deploy/backend --timeout=60s || warn "backend rollout slow"
  kubectl -n pla rollout status deploy/frontend --timeout=60s || warn "frontend rollout slow"
  ok "K8s pods are running"
else
  warn "kubectl not found — skipping K8s step"
fi

# 3. Ollama (local)
log "Checking Ollama..."
if curl -fsS http://localhost:11434/api/version >/dev/null 2>&1; then
  ok "Ollama already running"
else
  if command -v ollama >/dev/null 2>&1; then
    nohup ollama serve >"${LOG_DIR}/ollama.log" 2>&1 &
    sleep 3
    ok "Ollama started"
  else
    warn "ollama binary not found — install from https://ollama.com"
  fi
fi

# 4. Meridian options trading bot (FastAPI :8200)
if [[ "${NO_MERIDIAN}" -eq 0 ]]; then
  if curl -fsS http://localhost:8200/api/options-bot/config >/dev/null 2>&1; then
    ok "Meridian bot already running on :8200"
  else
    log "Starting Meridian options bot on :8200..."
    cd "${ROOT_DIR}/meridian/backend"
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8200 \
      >"${LOG_DIR}/meridian.log" 2>&1 &
    cd "${ROOT_DIR}"
    sleep 4
    if curl -fsS http://localhost:8200/api/options-bot/config >/dev/null 2>&1; then
      ok "Meridian bot started"
    else
      warn "Meridian bot did not respond — see ${LOG_DIR}/meridian.log"
    fi
  fi
fi

# 5. Trading-alerts dashboard (static :8201)
if [[ "${NO_FRONTEND}" -eq 0 ]]; then
  if lsof -ti :8201 >/dev/null 2>&1; then
    ok "Trading alerts dashboard already on :8201"
  else
    log "Starting trading alerts dashboard on :8201..."
    cd "${ROOT_DIR}/meridian/frontend"
    nohup python3 -m http.server 8201 >"${LOG_DIR}/alerts.log" 2>&1 &
    cd "${ROOT_DIR}"
    sleep 1
    ok "Dashboard at http://localhost:8201/trading-alerts.html"
  fi
fi

echo
ok "AVIRA stack online"
echo "  - Frontend (K8s):      http://localhost:5173  (vite) / cluster ingress"
echo "  - Backend  (K8s):      http://localhost:30000"
echo "  - Meridian options:    http://localhost:8200"
echo "  - Alerts dashboard:    http://localhost:8201/trading-alerts.html"
echo "  - Ollama:              http://localhost:11434"
echo
echo "Logs: ${LOG_DIR}"
echo "Stop with:  ./scripts/avira-stop.sh"
