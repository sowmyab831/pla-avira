#!/bin/bash

# Personal Life Assistant - Run Backend Locally on Mac with GPU
# This script sets up and runs the backend with Metal GPU acceleration

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"

echo "=========================================="
echo "Personal Life Assistant - Backend (Local GPU)"
echo "=========================================="
echo ""

# Check Python
echo "[1/4] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

# Create virtual environment if it doesn't exist
echo "[2/4] Setting up virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Always source the virtual environment
source "$VENV_DIR/bin/activate"

# Install dependencies if venv was just created
if [ ! -f "$VENV_DIR/bin/uvicorn" ]; then
    echo "Installing dependencies..."
    pip install --upgrade pip setuptools wheel > /dev/null 2>&1
    pip install -e . > /dev/null 2>&1
    echo "✓ Dependencies installed"
fi

# Check GPU availability
echo "[3/4] Checking GPU availability..."
python3 -c "
import torch
if torch.backends.mps.is_available():
    print('✓ Metal GPU available')
    print(f'  PyTorch version: {torch.__version__}')
    print(f'  Device: mps')
    print(f'  Memory allocated: {torch.mps.current_allocated_memory()/1024**2:.2f} MB')
else:
    print('⚠ Metal GPU not available, falling back to CPU')
    print(f'  PyTorch version: {torch.__version__}')
    print('  Device: cpu')
"

# Set environment variables
export DEPLOYMENT_MODE=local
export PYTORCH_ENABLE_MPS_FALLBACK=1

# Set service URLs to localhost since we're port-forwarding
export DATABASE_URL="postgresql://pla_user:changeme@localhost:5432/pla_db"
export REDIS_URL="redis://localhost:6379/0"
export QDRANT_URL="http://localhost:6333"
export MEILI_URL="http://localhost:7700"
export OLLAMA_HOST="http://localhost:11434"

# Display configuration
echo ""
echo "[4/4] Starting Backend Server"
echo "Environment:"
echo "  DEPLOYMENT_MODE: $DEPLOYMENT_MODE"
echo "  Database: ${DATABASE_URL%%@*}"
echo "  Redis: $REDIS_URL"
echo "  Qdrant: $QDRANT_URL"
echo "  MeiliSearch: $MEILI_URL"
echo "  Ollama: $OLLAMA_HOST"
echo ""
echo "Make sure to:"
echo "  1. Port-forward K8s services"
echo "  2. Start Ollama: ollama serve"
echo ""
echo "Access:"
echo "  API: http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the FastAPI server
cd "$BACKEND_DIR"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload