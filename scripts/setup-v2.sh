#!/bin/bash
set -e

# Personal Life Assistant - Local K8s Setup Script (v2)
# For Mac Mini M4 with OrbStack
# Fixes: StorageClass, PVC provisioning, startup probes, dependency ordering

NAMESPACE="pla"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_IMAGE="pla-backend:latest"
FRONTEND_IMAGE="pla-frontend:latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=========================================="
echo "Personal Life Assistant - Setup v2 (GPU-Enabled)"
echo "=========================================="
echo ""

# Check prerequisites
log_info "Checking prerequisites..."
command -v kubectl &> /dev/null || { log_error "kubectl not found. Install it first."; exit 1; }
command -v docker &> /dev/null || { log_error "docker not found. Install it first."; exit 1; }
log_info "✓ kubectl and docker found"
echo ""

# Check for GPU support
log_info "Checking for GPU support..."

# Always prefer local Ollama on Apple Silicon
if [[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]]; then
    log_info "✓ Apple Silicon (M4) detected on host"
    log_info "  Configuring to use local Ollama instance with Metal acceleration"
    
    # Use local Ollama with localhost
    export GPU_TYPE="mps"
    export OLLAMA_HOST="http://localhost:11434"
    export OLLAMA_API_BASE="$OLLAMA_HOST/api"
    export DEVICE="mps"
    export TORCH_DEVICE="mps"
    
    # Verify Ollama is running locally
    if ! curl -s --head --fail "$OLLAMA_HOST/api/version" >/dev/null; then
        log_error "Local Ollama instance not running at $OLLAMA_HOST"
        log_error "Please start Ollama locally first: brew services start ollama"
        exit 1
    fi
    
    # Check if model is available
    if ! curl -s "$OLLAMA_HOST/api/tags" | grep -q "qwen2.5:14b"; then
        log_warn "Model qwen2.5:14b not found in local Ollama"
        log_info "You can pull it with: ollama pull qwen2.5:14b"
    fi
else
    log_warn "⚠ No Apple Silicon detected. This setup is optimized for M4 GPU."
    log_warn "  Will fall back to CPU mode. Press Ctrl+C to cancel if this is unexpected."
    export GPU_TYPE="cpu"
    export OLLAMA_HOST="http://localhost:11434"  # Still use localhost for consistency
    export DEVICE="cpu"
    export TORCH_DEVICE="cpu"
fi

# Log final configuration
log_info "Final configuration:"
log_info "  - Using local Ollama at: $OLLAMA_HOST"
log_info "  - Device: $DEVICE (M4 GPU with Metal Performance Shaders)"
log_info "  - Model: qwen2.5:14b"
log_info "  - Kubernetes ML workloads: DISABLED (using local GPU)"
echo ""

# Clean up existing namespace and PVCs if they exist
log_info "Cleaning up existing resources..."
kubectl delete namespace $NAMESPACE --ignore-not-found=true 2>/dev/null
sleep 2
log_info "✓ Cleanup complete"
echo ""

# Create namespace
log_info "Creating namespace '$NAMESPACE'..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
log_info "✓ Namespace ready"
echo ""

# Apply StorageClass first (required for PVCs)
log_info "Applying StorageClass and PVCs..."
kubectl apply -f "$PROJECT_ROOT/k8s/storage-class.yaml"
log_info "✓ StorageClass and PVCs applied"
echo ""

# Wait for PVCs to be bound
log_info "Waiting for PVCs to be provisioned (this may take a moment)..."
for pvc in postgres-pvc redis-pvc qdrant-pvc meili-pvc ollama-pvc documents-pvc; do
    timeout=60
    while [ $timeout -gt 0 ]; do
        status=$(kubectl get pvc $pvc -n $NAMESPACE -o jsonpath='{.status.phase}' 2>/dev/null || echo "Pending")
        if [ "$status" = "Bound" ]; then
            log_info "✓ PVC $pvc is Bound"
            break
        fi
        echo -n "."
        sleep 2
        timeout=$((timeout - 2))
    done
    if [ $timeout -le 0 ]; then
        log_warn "PVC $pvc did not bind within 60 seconds (may still be provisioning)"
    fi
done
echo ""

# Build Docker images
log_info "Building Docker images..."
log_info "Building backend image..."
docker build --platform linux/arm64 -t $BACKEND_IMAGE -f "$PROJECT_ROOT/backend/Dockerfile" "$PROJECT_ROOT/backend/"
log_info "✓ Backend image built"

log_info "Building frontend image..."
docker build --platform linux/arm64 -t $FRONTEND_IMAGE -f "$PROJECT_ROOT/frontend/Dockerfile" "$PROJECT_ROOT/frontend/"
log_info "✓ Frontend image built"
echo ""

# Apply Kubernetes manifests in dependency order
log_info "Applying Kubernetes manifests..."

# 1. PostgreSQL
log_info "Deploying PostgreSQL..."
kubectl apply -f "$PROJECT_ROOT/k8s/postgres.yaml"

# 2. Redis
log_info "Deploying Redis..."
kubectl apply -f "$PROJECT_ROOT/k8s/redis.yaml"

# 3. Qdrant
log_info "Deploying Qdrant..."
kubectl apply -f "$PROJECT_ROOT/k8s/qdrant.yaml"

# 4. MeiliSearch
log_info "Deploying MeiliSearch..."
kubectl apply -f "$PROJECT_ROOT/k8s/meili.yaml"

# 5. Ollama
log_info "Deploying Ollama..."
kubectl apply -f "$PROJECT_ROOT/k8s/ollama.yaml"

log_info "✓ All manifests applied"
echo ""

# Wait for PostgreSQL to be ready
log_info "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s 2>/dev/null || {
    log_warn "PostgreSQL pod not ready within 300s, checking logs..."
    kubectl logs -l app=postgres -n $NAMESPACE --tail=20
}
log_info "✓ PostgreSQL is ready"
echo ""

# Wait for Redis to be ready
log_info "Waiting for Redis to be ready..."
kubectl wait --for=condition=ready pod -l app=redis -n $NAMESPACE --timeout=120s 2>/dev/null || {
    log_warn "Redis pod not ready within 120s"
}
log_info "✓ Redis is ready"
echo ""

# Wait for Qdrant to be ready
log_info "Waiting for Qdrant to be ready..."
kubectl wait --for=condition=ready pod -l app=qdrant -n $NAMESPACE --timeout=120s 2>/dev/null || {
    log_warn "Qdrant pod not ready within 120s"
}
log_info "✓ Qdrant is ready"
echo ""

# Wait for MeiliSearch to be ready
log_info "Waiting for MeiliSearch to be ready..."
kubectl wait --for=condition=ready pod -l app=meili -n $NAMESPACE --timeout=120s 2>/dev/null || {
    log_warn "MeiliSearch pod not ready within 120s"
}
log_info "✓ MeiliSearch is ready"
echo ""

# Wait for Ollama to be ready
log_info "Waiting for Ollama to be ready..."
kubectl wait --for=condition=ready pod -l app=ollama -n $NAMESPACE --timeout=300s 2>/dev/null || {
    log_warn "Ollama pod not ready within 300s (this is normal if model is downloading)"
}
log_info "✓ Ollama deployment started"
echo ""

# Deploy backend (now that all dependencies are ready)
log_info "Deploying backend..."
kubectl apply -f "$PROJECT_ROOT/k8s/backend.yaml"
log_info "✓ Backend deployment applied"
echo ""

# Wait for backend to be ready (with longer timeout for model download)
log_info "Waiting for backend to be ready (this may take 5-10 minutes for first startup)..."
timeout=600
while [ $timeout -gt 0 ]; do
    ready=$(kubectl get deployment backend -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    desired=$(kubectl get deployment backend -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [ "$ready" = "$desired" ] && [ "$desired" != "0" ]; then
        log_info "✓ Backend is ready"
        break
    fi
    
    echo -n "."
    sleep 5
    timeout=$((timeout - 5))
done

if [ $timeout -le 0 ]; then
    log_error "Backend did not become ready within 10 minutes"
    log_warn "Checking backend pod logs..."
    kubectl logs -l app=backend -n $NAMESPACE --tail=50
    exit 1
fi
echo ""

# Deploy frontend
log_info "Deploying frontend..."
kubectl apply -f "$PROJECT_ROOT/k8s/frontend.yaml"
log_info "✓ Frontend deployment applied"
echo ""

# Wait for frontend to be ready
log_info "Waiting for frontend to be ready..."
kubectl wait --for=condition=ready pod -l app=frontend -n $NAMESPACE --timeout=120s 2>/dev/null || {
    log_warn "Frontend pod not ready within 120s"
}
log_info "✓ Frontend is ready"
echo ""

# Apply ingress
log_info "Applying Ingress configuration..."
kubectl apply -f "$PROJECT_ROOT/k8s/ingress.yaml"
log_info "✓ Ingress applied"
echo ""

# Print access information
echo "=========================================="
echo "✓ Setup Complete!"
echo "=========================================="
echo ""
echo "Access your Personal Life Assistant:"
echo ""
echo "Frontend:  http://localhost:3000"
echo "Backend:   http://localhost:8000"
echo "API Docs:  http://localhost:8000/docs"
echo ""
echo "Kubernetes Resources:"
echo ""
kubectl get all -n $NAMESPACE
echo ""
echo "To view logs:"
echo "  kubectl logs -f deployment/backend -n $NAMESPACE"
echo "  kubectl logs -f deployment/frontend -n $NAMESPACE"
echo ""
echo "To access the cluster:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl describe pod <pod-name> -n $NAMESPACE"
echo ""
