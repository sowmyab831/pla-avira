#!/usr/bin/env bash
# AVIRA Ollama model curator
# Lists current models, removes ones not in the recommended set, and pulls missing ones.
# Usage:
#   ./scripts/avira-models.sh           # audit only
#   ./scripts/avira-models.sh --apply   # actually prune + pull

set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

# ── Recommended model registry ───────────────────────────────────────────────
# Tuned for an Apple Silicon M4 16GB box doing finance + trading reasoning.
#
# qwen2.5:14b           → primary finance/structured-data reasoner   (9.3 GB)
# mistral:7b-instruct   → fast assistant + classifier                (4.4 GB)
# deepseek-r1:32b       → on-demand deep reasoner (slow but smart)   (20 GB)
# nomic-embed-text      → embeddings for RAG / vector search         (0.3 GB)
#
# (qwq:32b is essentially a slower duplicate of deepseek-r1:32b → drop.)
RECOMMENDED=(
  "qwen2.5:14b"
  "mistral:7b-instruct"
  "deepseek-r1:32b"
  "nomic-embed-text:latest"
)

c_red="\033[1;31m"; c_grn="\033[1;32m"; c_yel="\033[1;33m"; c_cyn="\033[1;36m"; c_off="\033[0m"

if ! curl -fsS http://localhost:11434/api/version >/dev/null 2>&1; then
  echo -e "${c_red}Ollama is not running on :11434${c_off}"
  echo "Start it with:  ollama serve  (or run ./scripts/avira-start.sh first)"
  exit 1
fi

mapfile -t INSTALLED < <(curl -s http://localhost:11434/api/tags | python3 -c "
import json,sys
print('\n'.join(m['name'] for m in json.load(sys.stdin).get('models',[])))
")

echo -e "${c_cyn}== AVIRA model audit ==${c_off}"
echo
echo "Installed:"
for m in "${INSTALLED[@]}"; do
  if printf '%s\n' "${RECOMMENDED[@]}" | grep -qx "$m"; then
    echo -e "  ${c_grn}✓ keep   ${c_off}$m"
  else
    echo -e "  ${c_red}✗ remove ${c_off}$m"
  fi
done

echo
echo "Recommended (will pull if missing):"
to_pull=()
for m in "${RECOMMENDED[@]}"; do
  if printf '%s\n' "${INSTALLED[@]}" | grep -qx "$m"; then
    echo -e "  ${c_grn}✓ have   ${c_off}$m"
  else
    echo -e "  ${c_yel}↓ pull   ${c_off}$m"
    to_pull+=("$m")
  fi
done

if [[ "${APPLY}" -ne 1 ]]; then
  echo
  echo -e "${c_yel}Audit only. Run with --apply to prune unused and pull missing.${c_off}"
  exit 0
fi

echo
echo -e "${c_cyn}-- Removing unused models --${c_off}"
for m in "${INSTALLED[@]}"; do
  if ! printf '%s\n' "${RECOMMENDED[@]}" | grep -qx "$m"; then
    echo "rm $m"
    ollama rm "$m" || true
  fi
done

echo
echo -e "${c_cyn}-- Pulling missing models --${c_off}"
for m in "${to_pull[@]}"; do
  echo "pull $m"
  ollama pull "$m"
done

echo
echo -e "${c_grn}Model curation complete.${c_off}"
