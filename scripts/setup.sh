#!/bin/bash
set -e

# Personal Life Assistant - Local K8s Setup Script
# For Mac Mini M4 with OrbStack

NAMESPACE="pla"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "Personal Life Assistant - Setup"
echo "=========================================="
echo ""

# Check prerequisites
echo "[1/6] Checking prerequisites..."
command -v kubectl &> /dev/null || { echo "kubectl not found. Install it first."; exit 1; }
command -v docker &> /dev/null || { echo "docker not found. Install it first."; exit 1; }
echo "✓ kubectl and docker found"
echo ""

# Create namespace
echo "[2/6] Creating Kubernetes namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo "✓ Namespace '$NAMESPACE' created/updated"
echo ""

# Create secrets
echo "[3/6] Setting up secrets..."
if [ -f "$PROJECT_ROOT/secrets/credentials.json" ]; then
    kubectl create secret generic google-creds \
        --from-file=credentials.json="$PROJECT_ROOT/secrets/credentials.json" \
        -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    echo "✓ Google credentials secret created"
else
    echo "⚠ Google credentials not found at $PROJECT_ROOT/secrets/credentials.json"
    echo "  Create this file if you plan to use Google Cloud services"
fi

# Create external LLM secrets (optional)
echo "⚠ External LLM secrets not configured. Set them manually:"
echo "  kubectl create secret generic external-llm-keys \\"
echo "    --from-literal=OPENAI_API_KEY=sk-... \\"
echo "    --from-literal=ANTHROPIC_API_KEY=sk-ant-... \\"
echo "    --from-literal=GEMINI_API_KEY=AIza... \\"
echo "    -n $NAMESPACE"
echo ""

# Build Docker images
echo "[4/6] Building Docker images..."
echo "Building backend image..."
docker build --platform linux/arm64 -t pla-backend:latest "$PROJECT_ROOT/backend"
echo "✓ Backend image built"

echo "Building frontend image..."
docker build --platform linux/arm64 -t pla-frontend:latest "$PROJECT_ROOT/frontend"
echo "✓ Frontend image built"
echo ""

# Apply K8s manifests
echo "[5/6] Applying Kubernetes manifests..."
kubectl apply -f "$PROJECT_ROOT/k8s/" -n $NAMESPACE
echo "✓ Manifests applied"
echo ""

# Wait for deployments
echo "[6/6] Waiting for services to be ready..."
echo "This may take 2-3 minutes..."

# Wait for postgres
echo "Waiting for PostgreSQL..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/postgres -n $NAMESPACE 2>/dev/null || echo "⚠ PostgreSQL timeout"

# Wait for redis
echo "Waiting for Redis..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/redis -n $NAMESPACE 2>/dev/null || echo "⚠ Redis timeout"

# Wait for qdrant
echo "Waiting for Qdrant..."
kubectl wait --for=condition=ready --timeout=300s \
    statefulset/qdrant -n $NAMESPACE 2>/dev/null || echo "⚠ Qdrant timeout"

# Wait for meili
echo "Waiting for MeiliSearch..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/meili -n $NAMESPACE 2>/dev/null || echo "⚠ MeiliSearch timeout"

# Wait for backend
echo "Waiting for Backend..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/backend -n $NAMESPACE 2>/dev/null || echo "⚠ Backend timeout"

# Wait for frontend
echo "Waiting for Frontend..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/frontend -n $NAMESPACE 2>/dev/null || echo "⚠ Frontend timeout"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""

# Get service URLs
echo "Service URLs:"
echo ""

BACKEND_PORT=$(kubectl get svc backend-nodeport -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "30000")
FRONTEND_PORT=$(kubectl get svc frontend-nodeport -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "30001")

echo "Frontend:  http://localhost:$FRONTEND_PORT"
echo "Backend:   http://localhost:$BACKEND_PORT"
echo "Health:    http://localhost:$BACKEND_PORT/health"
echo "Docs:      http://localhost:$BACKEND_PORT/docs"
echo ""

# Health checks
echo "Health Checks:"
echo ""

echo "Testing backend health..."
if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
    echo "✓ Backend is healthy"
else
    echo "⚠ Backend health check failed (may still be starting)"
fi

echo ""
echo "Next steps:"
echo "1. Check pod status: kubectl get pods -n $NAMESPACE"
echo "2. View logs: kubectl logs -f deployment/backend -n $NAMESPACE"
echo "3. Access frontend: http://localhost:$FRONTEND_PORT"
echo "4. Access API docs: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "To clean up: kubectl delete namespace $NAMESPACE"
echo ""
