#!/bin/bash
set -e

# Personal Life Assistant - K8s Only Deployment
# Deploys only K8s services (no backend)
# Backend runs locally on Mac with GPU

NAMESPACE="pla"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "Personal Life Assistant - K8s Services Only"
echo "=========================================="
echo ""
echo "This deployment includes:"
echo "  ✓ PostgreSQL"
echo "  ✓ Redis"
echo "  ✓ Qdrant"
echo "  ✓ MeiliSearch"
echo "  ✓ Frontend (Nginx)"
echo ""
echo "Backend runs locally on Mac with GPU"
echo "Ollama runs locally on Mac with GPU"
echo ""

# Check prerequisites
echo "[1/4] Checking prerequisites..."
command -v kubectl &> /dev/null || { echo "ERROR: kubectl not found"; exit 1; }
echo "✓ kubectl found"
echo ""

# Clean and create namespace
echo "[2/4] Setting up namespace..."
kubectl delete namespace $NAMESPACE --ignore-not-found=true 2>/dev/null
sleep 1
kubectl create namespace $NAMESPACE
kubectl apply -f "$PROJECT_ROOT/k8s/storage-class.yaml"
echo "✓ Namespace and storage ready"
echo ""

# Deploy K8s services only
echo "[3/4] Deploying K8s services..."
kubectl apply -f "$PROJECT_ROOT/k8s/postgres.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/redis.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/qdrant.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/meili.yaml"
kubectl apply -f "$PROJECT_ROOT/k8s/frontend.yaml"
echo "✓ All K8s services deployed"
echo ""

# Wait for services
echo "[4/4] Waiting for services to be ready..."
echo "  (This may take 2-3 minutes)"
echo ""

# Wait for postgres
echo "  Waiting for PostgreSQL..."
timeout=120
while [ $timeout -gt 0 ]; do
    ready=$(kubectl get deployment postgres -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$ready" = "1" ]; then
        echo "  ✓ PostgreSQL ready"
        break
    fi
    echo -n "."
    sleep 2
    timeout=$((timeout - 2))
done

# Wait for redis
echo "  Waiting for Redis..."
timeout=60
while [ $timeout -gt 0 ]; do
    ready=$(kubectl get deployment redis -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$ready" = "1" ]; then
        echo "  ✓ Redis ready"
        break
    fi
    echo -n "."
    sleep 2
    timeout=$((timeout - 2))
done

# Wait for qdrant
echo "  Waiting for Qdrant..."
timeout=60
while [ $timeout -gt 0 ]; do
    ready=$(kubectl get statefulset qdrant -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$ready" = "1" ]; then
        echo "  ✓ Qdrant ready"
        break
    fi
    echo -n "."
    sleep 2
    timeout=$((timeout - 2))
done

# Wait for meili
echo "  Waiting for MeiliSearch..."
timeout=60
while [ $timeout -gt 0 ]; do
    ready=$(kubectl get deployment meili -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$ready" = "1" ]; then
        echo "  ✓ MeiliSearch ready"
        break
    fi
    echo -n "."
    sleep 2
    timeout=$((timeout - 2))
done

# Wait for frontend
echo "  Waiting for Frontend..."
timeout=60
while [ $timeout -gt 0 ]; do
    ready=$(kubectl get deployment frontend -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$ready" = "1" ]; then
        echo "  ✓ Frontend ready"
        break
    fi
    echo -n "."
    sleep 2
    timeout=$((timeout - 2))
done

echo ""
echo "=========================================="
echo "✓ K8s Services Ready!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Port-forward services (in separate terminals):"
echo "   kubectl port-forward svc/postgres 5432:5432 -n pla"
echo "   kubectl port-forward svc/redis 6379:6379 -n pla"
echo "   kubectl port-forward svc/qdrant 6333:6333 -n pla"
echo "   kubectl port-forward svc/meili 7700:7700 -n pla"
echo ""
echo "2. Start Ollama on Mac:"
echo "   ollama serve"
echo ""
echo "3. Start Backend on Mac (in another terminal):"
echo "   cd $PROJECT_ROOT/backend"
echo "   source venv/bin/activate"
echo "   export DEPLOYMENT_MODE=local"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "4. Access application:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "Monitor K8s services:"
echo "  kubectl get pods -n pla -w"
echo "  kubectl logs -f deployment/postgres -n pla"
echo ""
