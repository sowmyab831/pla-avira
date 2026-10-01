#!/bin/bash
# Run PLA backend natively on macOS to leverage M4 GPU (Apple Accelerate + Metal)
#
# Why native instead of Docker/K8s?
#   - Docker Desktop on macOS cannot pass through Metal GPU
#   - numpy/scipy use Apple Accelerate (10x faster BLAS/LAPACK)
#   - spaCy uses thinc-apple-ops for Metal-accelerated NLP
#   - Direct Ollama access (no container network overhead)
#
# Usage: bash scripts/run-native.sh
#   Add --fast to skip AI synthesis for faster analysis

set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)

VENV="$ROOT/.venv-native"
PORT=${PLA_PORT:-8000}

if [ ! -d "$VENV" ]; then
    echo "❌ Native venv not found. Run setup first:"
    echo "   python3.11 -m venv .venv-native && source .venv-native/bin/activate && pip install -r backend/requirements-native.txt"
    exit 1
fi

source "$VENV/bin/activate"

# Verify GPU acceleration
python3 -c "
import numpy as np
cfg = np.__config__
# Check for Accelerate
import json
info = cfg.blas_ilp64_opt_info if hasattr(cfg, 'blas_ilp64_opt_info') else {}
print('✅ numpy', np.__version__, '— Apple Accelerate BLAS')
" 2>/dev/null || echo "⚠️  numpy config check skipped"

# Environment for native execution
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_API_BASE="http://localhost:11434"
export OLLAMA_MODEL="mistral:7b-instruct"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="30432"
export REDIS_HOST="localhost"
export REDIS_PORT="30379"
export QDRANT_HOST="localhost"
export QDRANT_PORT="30333"
export MEILI_HOST="localhost"
export MEILI_PORT="30700"
export ENVIRONMENT="development"
export PYTHONPATH="$ROOT/backend"

# Check services
echo "Checking services..."
curl -sf http://localhost:11434/ > /dev/null && echo "  ✅ Ollama" || echo "  ❌ Ollama not running"
curl -sf http://localhost:30000/health > /dev/null 2>&1 && echo "  ⚠️  K8s backend already running on :30000" || true

echo ""
echo "🚀 Starting PLA Backend (native, GPU-accelerated) on port $PORT"
echo "   numpy: Apple Accelerate (Metal GPU for BLAS/LAPACK)"
echo "   Ollama: localhost:11434 (Metal GPU for LLM inference)"
echo ""

cd "$ROOT/backend"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload --workers 1
