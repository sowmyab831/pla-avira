#!/usr/bin/env bash
# AVIRA stack status report
set -uo pipefail

c_red="\033[1;31m"; c_grn="\033[1;32m"; c_yel="\033[1;33m"; c_cyn="\033[1;36m"; c_off="\033[0m"

check_url() {
  local label="$1" url="$2"
  if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
    echo -e "${c_grn}● UP  ${c_off}${label}  ${url}"
  else
    echo -e "${c_red}○ DOWN${c_off}  ${label}  ${url}"
  fi
}

echo -e "${c_cyn}== AVIRA stack status ==${c_off}"

# OrbStack
if command -v orbctl >/dev/null 2>&1; then
  if orbctl status 2>/dev/null | grep -qi running; then
    echo -e "${c_grn}● UP  ${c_off}OrbStack"
  else
    echo -e "${c_red}○ DOWN${c_off} OrbStack"
  fi
fi

# K8s
if command -v kubectl >/dev/null 2>&1; then
  echo -e "${c_cyn}-- K8s pla namespace --${c_off}"
  kubectl -n pla get pods --no-headers 2>/dev/null | awk '{
    color=($3=="Running" || $3=="Completed") ? "\033[1;32m" : "\033[1;31m";
    printf "%s● %-7s\033[0m %-40s %s\n", color, $3, $1, $2
  }' || echo "  (cluster unreachable)"
fi

echo -e "${c_cyn}-- Local services --${c_off}"
check_url "Ollama         " "http://localhost:11434/api/version"
check_url "Backend (K8s)  " "http://localhost:30000/health"
check_url "Frontend (vite)" "http://localhost:5173"
check_url "Meridian bot   " "http://localhost:8200/api/options-bot/config"
check_url "Alerts dashbd  " "http://localhost:8201/trading-alerts.html"

# Ollama models
if curl -fsS --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo -e "${c_cyn}-- Ollama models --${c_off}"
  curl -s http://localhost:11434/api/tags | python3 -c "
import json,sys
d=json.load(sys.stdin)
for m in d.get('models',[]):
    sz=m.get('size',0)/1024/1024/1024
    print(f'  {m[\"name\"]:<30} {sz:5.1f} GB')
" 2>/dev/null || true
fi
