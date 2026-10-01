#!/usr/bin/env bash
# OpenClaw + PLA Avira Setup Script
# Installs OpenClaw, links the PLA workspace, and configures the gateway.
#
# Prerequisites:
#   - Node.js >= 22
#   - PLA backend running on localhost:30000
#   - Ollama running on localhost:11434

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLA_ROOT="$(dirname "$SCRIPT_DIR")"

echo "═══════════════════════════════════════════"
echo "  OpenClaw + PLA Avira Setup"
echo "═══════════════════════════════════════════"

# Check Node.js
if ! command -v node &>/dev/null; then
  echo "❌ Node.js not found. Install Node >= 22:"
  echo "   brew install node@22"
  exit 1
fi

NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VER" -lt 22 ]; then
  echo "⚠️  Node $NODE_VER found, need >= 22. Upgrade:"
  echo "   brew install node@22"
  exit 1
fi
echo "✓ Node.js $(node -v)"

# Install OpenClaw
if ! command -v openclaw &>/dev/null; then
  echo "→ Installing OpenClaw..."
  npm install -g openclaw@latest
else
  echo "✓ OpenClaw already installed ($(openclaw --version 2>/dev/null || echo 'unknown'))"
fi

# Link pla CLI tool to PATH
PLA_CLI="$SCRIPT_DIR/workspace/tools/pla"
if [ -f "$PLA_CLI" ]; then
  chmod +x "$PLA_CLI"
  # Symlink to a PATH location
  if [ -d "$HOME/.local/bin" ]; then
    ln -sf "$PLA_CLI" "$HOME/.local/bin/pla"
    echo "✓ pla CLI linked to ~/.local/bin/pla"
  elif [ -d "/usr/local/bin" ]; then
    ln -sf "$PLA_CLI" "/usr/local/bin/pla"
    echo "✓ pla CLI linked to /usr/local/bin/pla"
  else
    mkdir -p "$HOME/.local/bin"
    ln -sf "$PLA_CLI" "$HOME/.local/bin/pla"
    echo "✓ pla CLI linked to ~/.local/bin/pla"
    echo "   Add to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
  fi
fi

# Copy OpenClaw config
OPENCLAW_DIR="$HOME/.openclaw"
mkdir -p "$OPENCLAW_DIR"

if [ ! -f "$OPENCLAW_DIR/openclaw.json" ]; then
  cp "$SCRIPT_DIR/openclaw.json" "$OPENCLAW_DIR/openclaw.json"
  echo "✓ OpenClaw config installed"
else
  echo "✓ OpenClaw config already exists (not overwriting)"
fi

# Link workspace
WORKSPACE_DIR="$OPENCLAW_DIR/workspace"
if [ -L "$WORKSPACE_DIR" ] || [ -d "$WORKSPACE_DIR" ]; then
  echo "✓ Workspace already exists"
else
  ln -sf "$SCRIPT_DIR/workspace" "$WORKSPACE_DIR"
  echo "✓ PLA workspace linked to OpenClaw"
fi

# Check PLA backend
echo ""
echo "Checking PLA backend..."
if curl -sf http://localhost:30000/health &>/dev/null; then
  echo "✓ PLA backend is running"
else
  echo "⚠️  PLA backend not reachable at localhost:30000"
  echo "   Start it: kubectl apply -f k8s/ (or docker-compose up)"
fi

# Check Ollama
echo ""
echo "Checking Ollama..."
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
  echo "✓ Ollama is running"
  MODELS=$(curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; [print(f'  - {m[\"name\"]}') for m in json.loads(sys.stdin.read()).get('models',[])]" 2>/dev/null || echo "  (could not list models)")
  echo "$MODELS"
else
  echo "⚠️  Ollama not reachable at localhost:11434"
  echo "   Install: brew install ollama && ollama serve"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Start OpenClaw:"
echo "    openclaw onboard --install-daemon"
echo ""
echo "  Or run gateway directly:"
echo "    openclaw gateway --verbose"
echo ""
echo "  Test pla CLI:"
echo "    pla health"
echo "    pla stock AAPL"
echo "    pla shop \"organic chicken\""
echo "═══════════════════════════════════════════"
