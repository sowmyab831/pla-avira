#!/usr/bin/env bash
# AVIRA Stop Orchestrator
# Stops: trading dashboard, meridian bot, scales K8s pods to 0 (optional), ollama (optional)
# Usage: ./scripts/avira-stop.sh [--scale-pods] [--stop-ollama] [--stop-orb]

set -euo pipefail

SCALE_PODS=0
STOP_OLLAMA=0
STOP_ORB=0
for arg in "$@"; do
  case "$arg" in
    --scale-pods) SCALE_PODS=1 ;;
    --stop-ollama) STOP_OLLAMA=1 ;;
    --stop-orb) STOP_ORB=1 ;;
    --all) SCALE_PODS=1; STOP_OLLAMA=1; STOP_ORB=1 ;;
  esac
done

log()  { printf "\033[1;36m[avira]\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m[ ok ]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    sleep 1
    pids="$(lsof -ti :"$port" 2>/dev/null || true)"
    [[ -n "$pids" ]] && echo "$pids" | xargs kill -9 2>/dev/null || true
    ok "Stopped port :$port"
  fi
}

log "Stopping trading alerts dashboard (:8201)..."
kill_port 8201

log "Stopping Meridian options bot (:8200)..."
kill_port 8200

if [[ "${SCALE_PODS}" -eq 1 ]] && command -v kubectl >/dev/null 2>&1; then
  log "Scaling K8s pla pods to 0..."
  for d in backend frontend meili redis postgres ldap; do
    if kubectl -n pla get deploy "$d" >/dev/null 2>&1; then
      kubectl -n pla scale deploy/"$d" --replicas=0 >/dev/null 2>&1 || true
    fi
  done
  if kubectl -n pla get statefulset qdrant >/dev/null 2>&1; then
    kubectl -n pla scale statefulset/qdrant --replicas=0 >/dev/null 2>&1 || true
  fi
  ok "K8s pods scaled to 0 (data preserved on PVCs)"
fi

if [[ "${STOP_OLLAMA}" -eq 1 ]]; then
  log "Stopping Ollama..."
  pkill -f "ollama serve" 2>/dev/null || true
  pkill -f "ollama runner" 2>/dev/null || true
  ok "Ollama stopped"
fi

if [[ "${STOP_ORB}" -eq 1 ]] && command -v orbctl >/dev/null 2>&1; then
  log "Stopping OrbStack..."
  orbctl stop || warn "OrbStack stop reported non-zero"
fi

ok "AVIRA stack stopped"
echo
echo "Tip:  ./scripts/avira-stop.sh --all   stops pods, Ollama, and OrbStack"
echo "Tip:  ./scripts/avira-start.sh        brings everything back online"
