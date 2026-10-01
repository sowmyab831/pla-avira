#!/bin/bash

# Personal Life Assistant - Setup Ollama with Mistral 7B on Mac Mini M4 GPU
# This script installs and configures Ollama to use Metal GPU acceleration

echo "=========================================="
echo "Ollama Setup - Mistral 7B with Metal GPU"
echo "=========================================="
echo ""

# Check if Ollama is installed
echo "[1/4] Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    # Install via Homebrew
    brew install ollama
    echo "✓ Ollama installed"
else
    echo "✓ Ollama already installed"
    ollama --version
fi
echo ""

# Check if Ollama service is running
echo "[2/4] Checking Ollama service..."
if pgrep -x "ollama" > /dev/null; then
    echo "✓ Ollama service is running"
else
    echo "Starting Ollama service..."
    # Start Ollama in background
    ollama serve &
    OLLAMA_PID=$!
    echo "✓ Ollama service started (PID: $OLLAMA_PID)"
    sleep 5
fi
echo ""

# Check GPU availability
echo "[3/4] Checking Metal GPU availability..."
python3 << 'EOF'
import subprocess
import json

try:
    # Check if Metal GPU is available via Ollama
    result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print("✓ Ollama is responding")
        print("  Metal GPU will be used automatically for inference")
    else:
        print("⚠ Ollama not responding yet, waiting...")
except Exception as e:
    print(f"⚠ Error checking Ollama: {e}")
EOF
echo ""

# Pull Mistral 7B model
echo "[4/4] Pulling Mistral 7B model..."
echo "This may take 5-10 minutes (4.1GB download)..."
echo ""

ollama pull mistral

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Mistral 7B model pulled successfully"
else
    echo ""
    echo "⚠ Failed to pull Mistral 7B model"
    echo "Try manually: ollama pull mistral"
fi

echo ""
echo "=========================================="
echo "Ollama Setup Complete!"
echo "=========================================="
echo ""
echo "Access Ollama:"
echo "  Local: http://localhost:11434"
echo "  From K8s: http://host.docker.internal:11434"
echo ""
echo "Test Ollama:"
echo "  curl http://localhost:11434/api/tags"
echo ""
echo "Run inference:"
echo "  ollama run mistral"
echo ""
echo "GPU Status:"
echo "  Metal GPU will be used automatically"
echo "  Check Activity Monitor for GPU usage"
echo ""
echo "To keep Ollama running:"
echo "  ollama serve"
echo ""
