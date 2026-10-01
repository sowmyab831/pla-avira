# Enterprise Deployment Guide - Avira PLA

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Devices                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Web      │  │ iOS App  │  │ Android  │  │ Mobile   │   │
│  │ Browser  │  │          │  │ App      │  │ Browser  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Ingress (Port 80/443)    │
        │   nginx-ingress-controller │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Kubernetes Cluster       │
        │   (OrbStack on Mac M4)     │
        │                            │
        │  ┌──────────────────────┐  │
        │  │  Frontend Pods (2x)  │  │
        │  │  React + Vite        │  │
        │  │  Port: 80            │  │
        │  └──────────┬───────────┘  │
        │             │              │
        │  ┌──────────▼───────────┐  │
        │  │  Backend Pod         │  │
        │  │  FastAPI + Python    │  │
        │  │  Port: 8000          │  │
        │  │  hostNetwork: true   │◄─┼─── Accesses localhost:11434
        │  └──────────┬───────────┘  │
        │             │              │
        │  ┌──────────▼───────────┐  │
        │  │  PostgreSQL Pod      │  │
        │  │  Port: 5432          │  │
        │  └──────────────────────┘  │
        │                            │
        │  ┌──────────────────────┐  │
        │  │  Redis Pod           │  │
        │  │  Port: 6379          │  │
        │  └──────────────────────┘  │
        │                            │
        │  ┌──────────────────────┐  │
        │  │  Qdrant Pod          │  │
        │  │  Vector DB           │  │
        │  │  Port: 6333          │  │
        │  └──────────────────────┘  │
        │                            │
        │  ┌──────────────────────┐  │
        │  │  MeiliSearch Pod     │  │
        │  │  Full-text Search    │  │
        │  │  Port: 7700          │  │
        │  └──────────────────────┘  │
        └────────────────────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Mac M4 Host Machine      │
        │                            │
        │  ┌──────────────────────┐  │
        │  │  Ollama Service      │  │
        │  │  llama3.3:70b        │  │
        │  │  Port: 11434         │  │
        │  │  GPU: Metal (M4)     │  │
        │  └──────────────────────┘  │
        └────────────────────────────┘
```

## Deployment Steps

### 1. Prerequisites Check

```bash
# Verify OrbStack is running
orbctl status

# Verify Kubernetes cluster
kubectl cluster-info

# Verify Ollama is running with GPU
ollama list
ps aux | grep ollama

# Check GPU availability
sudo powermetrics --samplers gpu_power -i 1000 -n 1
```

### 2. Build Docker Images

```bash
cd /Users/harish/Documents/code/pla-avira

# Build backend image (ARM64 for Mac M4)
cd backend
docker build --platform linux/arm64 -t pla-backend:latest .

# Build frontend image
cd ../frontend
docker build --platform linux/arm64 -t pla-frontend:latest .

# Verify images
docker images | grep pla
```

### 3. Deploy to Kubernetes

```bash
# Create namespace if not exists
kubectl create namespace pla --dry-run=client -o yaml | kubectl apply -f -

# Deploy all services
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/qdrant.yaml
kubectl apply -f k8s/meili.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n pla --timeout=600s

# Check deployment status
kubectl get pods -n pla
kubectl get svc -n pla
```

### 4. Initialize Database

```bash
# Get backend pod name
BACKEND_POD=$(kubectl get pods -n pla -l app=backend -o jsonpath='{.items[0].metadata.name}')

# Initialize admin account
kubectl exec -it $BACKEND_POD -n pla -- curl -X POST http://localhost:8000/api/auth/init-admin

# Verify health
kubectl exec -it $BACKEND_POD -n pla -- curl http://localhost:8000/health
```

### 5. Access the Application

**Web UI:**
```bash
# Via NodePort (local development)
open http://localhost:30001

# Via Ingress (production)
open http://avira.local
```

**API:**
```bash
# Via NodePort
curl http://localhost:30000/health

# Via Ingress
curl http://avira.local/api/health
```

**API Documentation:**
```bash
open http://localhost:30000/docs
```

### 6. Mobile App Deployment

#### iOS App

```bash
cd mobileapp

# Install dependencies
npm install

# Update app.json with production API URL
# Edit: "apiUrl": "http://YOUR_DOMAIN:30000"

# Build for iOS
npx expo prebuild --platform ios

# Run on simulator
npx expo run:ios

# Build for App Store
eas build --platform ios --profile production
```

#### Android App

```bash
cd mobileapp

# Build for Android
npx expo prebuild --platform android

# Run on emulator
npx expo run:android

# Build APK for Play Store
eas build --platform android --profile production
```

### 7. Configure Ollama for K8s Access

The backend pod uses `hostNetwork: true` to access Ollama on localhost:11434. This allows the pod to use the Mac M4's GPU via Ollama.

**Verify Ollama is accessible:**
```bash
# From backend pod
kubectl exec -it $BACKEND_POD -n pla -- curl http://localhost:11434/api/tags

# Test model
kubectl exec -it $BACKEND_POD -n pla -- curl http://localhost:11434/api/generate \
  -d '{"model": "llama3.3:70b-instruct-q4_K_M", "prompt": "Hello", "stream": false}'
```

## Monitoring & Troubleshooting

### Check Logs

```bash
# Backend logs
kubectl logs -f -n pla -l app=backend

# Frontend logs
kubectl logs -f -n pla -l app=frontend

# Database logs
kubectl logs -f -n pla -l app=postgres

# All pods
kubectl logs -f -n pla --all-containers=true
```

### Common Issues

#### 1. Backend Pod in Error State

```bash
# Check pod events
kubectl describe pod -n pla -l app=backend

# Check init containers
kubectl logs -n pla -l app=backend -c wait-for-postgres

# Restart deployment
kubectl rollout restart deployment/backend -n pla
```

#### 2. Ollama Connection Issues

```bash
# Verify Ollama is running
ps aux | grep ollama

# Check if port 11434 is open
lsof -i :11434

# Test from host
curl http://localhost:11434/api/tags

# Restart Ollama if needed
brew services restart ollama
```

#### 3. Database Connection Issues

```bash
# Check PostgreSQL pod
kubectl get pods -n pla -l app=postgres

# Test connection
kubectl exec -it -n pla $(kubectl get pods -n pla -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- psql -U pla_user -d pla_db -c "SELECT 1"

# Check password in secret
kubectl get secret -n pla postgres-secret -o jsonpath='{.data.password}' | base64 -d
```

#### 4. Frontend Not Loading

```bash
# Check frontend pods
kubectl get pods -n pla -l app=frontend

# Check service
kubectl get svc -n pla frontend-nodeport

# Test directly
curl http://localhost:30001
```

## Performance Optimization

### 1. GPU Utilization

Monitor GPU usage while making AI requests:

```bash
# Monitor GPU in real-time
sudo powermetrics --samplers gpu_power -i 1000

# Check Ollama GPU usage
ollama ps
```

### 2. Resource Limits

Current resource allocation:

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Backend | 2000m | 4000m | 2Gi | 4Gi |
| Frontend | 100m | 500m | 128Mi | 512Mi |
| PostgreSQL | 500m | 1000m | 512Mi | 2Gi |
| Redis | 100m | 500m | 128Mi | 512Mi |
| Qdrant | 500m | 2000m | 512Mi | 2Gi |
| MeiliSearch | 500m | 1000m | 512Mi | 1Gi |

### 3. Scaling

```bash
# Scale frontend for high traffic
kubectl scale deployment frontend -n pla --replicas=3

# Scale backend (limited by GPU access)
# Note: Only 1 backend replica recommended due to hostNetwork

# Auto-scaling (future)
kubectl autoscale deployment frontend -n pla --min=2 --max=10 --cpu-percent=80
```

## Security Hardening

### 1. Change Default Passwords

```bash
# Update PostgreSQL password
kubectl create secret generic postgres-secret \
  --from-literal=password='YOUR_SECURE_PASSWORD' \
  -n pla --dry-run=client -o yaml | kubectl apply -f -

# Update MeiliSearch master key
kubectl set env deployment/backend -n pla MEILI_MASTER_KEY='YOUR_SECURE_KEY'

# Restart affected pods
kubectl rollout restart deployment/backend -n pla
kubectl rollout restart deployment/postgres -n pla
```

### 2. Enable TLS/SSL

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create certificate issuer
kubectl apply -f k8s/cert-issuer.yaml

# Update ingress with TLS
kubectl apply -f k8s/ingress-tls.yaml
```

### 3. Network Policies

```bash
# Apply network policies to restrict pod-to-pod communication
kubectl apply -f k8s/network-policies.yaml
```

## Backup & Recovery

### 1. Database Backup

```bash
# Create backup
kubectl exec -n pla $(kubectl get pods -n pla -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- \
  pg_dump -U pla_user pla_db > backup-$(date +%Y%m%d).sql

# Restore backup
kubectl exec -i -n pla $(kubectl get pods -n pla -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U pla_user pla_db < backup-20260201.sql
```

### 2. Volume Snapshots

```bash
# List persistent volumes
kubectl get pv

# Create snapshot (if supported by storage class)
kubectl apply -f k8s/volume-snapshot.yaml
```

## Production Deployment Checklist

- [ ] All services running and healthy
- [ ] Database initialized with admin account
- [ ] Default passwords changed
- [ ] TLS/SSL certificates configured
- [ ] Backup strategy implemented
- [ ] Monitoring and alerting setup
- [ ] Resource limits tuned
- [ ] Network policies applied
- [ ] API rate limiting configured
- [ ] CORS origins restricted
- [ ] Mobile apps built and tested
- [ ] Documentation updated
- [ ] Disaster recovery plan documented

## Maintenance

### Regular Tasks

**Daily:**
- Check pod health: `kubectl get pods -n pla`
- Monitor logs for errors
- Verify Ollama GPU usage

**Weekly:**
- Database backup
- Review resource usage
- Update dependencies

**Monthly:**
- Security patches
- Performance optimization
- Capacity planning

### Updates

```bash
# Update backend
cd backend
docker build --platform linux/arm64 -t pla-backend:latest .
kubectl rollout restart deployment/backend -n pla

# Update frontend
cd frontend
docker build --platform linux/arm64 -t pla-frontend:latest .
kubectl rollout restart deployment/frontend -n pla

# Verify rollout
kubectl rollout status deployment/backend -n pla
kubectl rollout status deployment/frontend -n pla
```

## Support & Troubleshooting

### Health Checks

```bash
# Overall health
curl http://localhost:30000/health | jq

# Individual services
kubectl exec -it $BACKEND_POD -n pla -- curl http://postgres:5432
kubectl exec -it $BACKEND_POD -n pla -- curl http://redis:6379
kubectl exec -it $BACKEND_POD -n pla -- curl http://qdrant:6333
kubectl exec -it $BACKEND_POD -n pla -- curl http://meili:7700/health
kubectl exec -it $BACKEND_POD -n pla -- curl http://localhost:11434
```

### Performance Metrics

```bash
# Pod resource usage
kubectl top pods -n pla

# Node resource usage
kubectl top nodes

# Detailed metrics
kubectl describe node
```

---

**Last Updated:** February 1, 2026
**Version:** 1.0.0
**Status:** Production Ready
