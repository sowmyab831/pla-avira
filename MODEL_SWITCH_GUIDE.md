# Ollama Model Switching Guide

## Current Configuration

**Active Model:** mistral:7b-instruct (4.9GB)
- Fast responses (5-15 seconds)
- Good quality analysis
- GPU usage: 18-27%

**Available Models:**
- `mistral:7b-instruct` - Fast, good quality (recommended for production)
- `llama3.3:70b-instruct-q4_K_M` - Slow (2min+), excellent quality (use for batch processing)
- `llama3.2:3b` - Very fast, basic quality

---

## How to Switch Models

### Method 1: Kubernetes Deployment (Recommended)

```bash
# Switch to 70B model
kubectl set env deployment/backend -n pla OLLAMA_MODEL="llama3.3:70b-instruct-q4_K_M"

# Switch back to mistral
kubectl set env deployment/backend -n pla OLLAMA_MODEL="mistral:7b-instruct"

# Verify change
kubectl get deployment backend -n pla -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="OLLAMA_MODEL")].value}'
```

### Method 2: Local Backend

```bash
# Set environment variable
export OLLAMA_MODEL="llama3.3:70b-instruct-q4_K_M"

# Restart backend
cd backend
./venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 30000 --reload
```

### Method 3: Update K8s Manifest

Edit `k8s/backend.yaml`:
```yaml
- name: OLLAMA_MODEL
  value: "llama3.3:70b-instruct-q4_K_M"  # Change this line
```

Then apply:
```bash
kubectl apply -f k8s/backend.yaml
kubectl delete pod -n pla -l app=backend
```

---

## Model Comparison

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| mistral:7b | 4.9GB | ⚡ Fast (5-15s) | ⭐⭐⭐⭐ Good | Production, real-time |
| llama3.3:70b | 42GB | 🐌 Slow (2min+) | ⭐⭐⭐⭐⭐ Excellent | Batch, detailed analysis |
| llama3.2:3b | 2GB | ⚡⚡ Very Fast (2-5s) | ⭐⭐⭐ Basic | Quick responses |

---

## Recommendations

**For Production:**
- Use `mistral:7b-instruct` for real-time user requests
- Use `llama3.3:70b` for overnight batch analysis
- Use `llama3.2:3b` for simple queries

**Current Setup:**
- Backend configured with `mistral:7b-instruct`
- Provides good balance of speed and quality
- GPU-accelerated (18-27% usage)

---

## Verify Model in Use

```bash
# Check Ollama
ollama ps

# Check backend logs
kubectl logs -f -n pla -l app=backend | grep "model"

# Test API
curl -s http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive | jq '.ai_recommendation'
```
