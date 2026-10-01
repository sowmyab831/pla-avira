#!/bin/bash
set -e

# Personal Life Assistant - GPU Deployment Script
# Simplified version for faster deployment

NAMESPACE="pla"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "Personal Life Assistant - GPU Deploy"
echo "=========================================="
echo ""

# Check prerequisites
echo "[1/5] Checking prerequisites..."
command -v kubectl &> /dev/null || { echo "ERROR: kubectl not found"; exit 1; }
command -v docker &> /dev/null || { echo "ERROR: docker not found"; exit 1; }
echo "✓ kubectl and docker found"
echo ""

# Clean and create namespace
echo "[2/5] Setting up namespace..."
kubectl delete namespace $NAMESPACE --ignore-not-found=true 2>/dev/null
sleep 1
kubectl create namespace $NAMESPACE
kubectl apply -f "$PROJECT_ROOT/k8s/storage-class.yaml"
echo "✓ Namespace and storage ready"
echo ""

# Build images
echo "[3/5] Building Docker images..."
echo "  Building backend (with GPU support)..."
docker build --platform linux/arm64 -t pla-backend:gpu -f "$PROJECT_ROOT/backend/Dockerfile" "$PROJECT_ROOT/backend/" > /dev/null 2>&1
echo "  ✓ Backend built"

echo "  Building frontend..."
docker build --platform linux/arm64 -t pla-frontend:latest -f "$PROJECT_ROOT/frontend/Dockerfile" "$PROJECT_ROOT/frontend/" > /dev/null 2>&1
echo "  ✓ Frontend built"
echo ""

# Deploy services
echo "[4/5] Deploying services..."
kubectl apply -f "$PROJECT_ROOT/k8s/postgres.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/redis.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/qdrant.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/meili.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/ollama.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/backend.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/frontend.yaml"
echo "✓ All services deployed"
echo ""

# Wait for readiness
echo "[5/5] Waiting for services to be ready..."
echo "  (This may take 5-10 minutes on first run)"
echo ""

# Wait for backend
echo "  Waiting for backend..."
timeout=600
while [ $timeout -gt 0 ]; do
    ready=$(kubectl get deployment backend -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    desired=$(kubectl get deployment backend -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [ "$ready" = "$desired" ] && [ "$desired" != "0" ]; then
        echo "  ✓ Backend ready"
        break
    fi
    
    echo -n "."
    sleep 5
    timeout=$((timeout - 5))
done

if [ $timeout -le 0 ]; then
    echo ""
    echo "ERROR: Backend did not become ready"
    kubectl logs -l app=backend -n $NAMESPACE --tail=20
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Deployment Complete!"
echo "=========================================="
echo ""
echo "Access your application:"
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "Check GPU usage:"
echo "  kubectl logs deployment/backend -n $NAMESPACE | grep -i cuda"
echo ""
echo "View all resources:"
echo "  kubectl get all -n $NAMESPACE"
echo ""
