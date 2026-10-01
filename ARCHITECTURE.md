# Architecture Overview

## System Design

```
┌──────────────────────────────────────────────────────────────────┐
│  User Channels (OpenClaw)                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ WhatsApp · Telegram · iMessage · Signal · Slack · Discord │  │
│  │ iOS Node · Android Node · macOS App · WebChat · Voice     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                       ↓ ws://127.0.0.1:18789                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ OpenClaw Gateway (Node.js, local-first)                    │  │
│  │ Skills: finance · shopping · travel · documents · calendar │  │
│  │ Tools: pla CLI → curl → PLA Backend REST API               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↓ HTTP (localhost)
┌──────────────────────────────────────────────────────────────────┐
│  React Frontend (Web UI — optional, also served via Nginx)       │
│  Dashboard | Chat | Finance | Health | School | Calendar         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (Python) — Domain Engine                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Routes:                                                    │  │
│  │ - /api/documents/secure/* (privacy pipeline)              │  │
│  │ - /api/portfolio/* (stocks, options, resilience)           │  │
│  │ - /api/shopping/* (multi-retailer search)                 │  │
│  │ - /api/travel/* (flights, hotels)                         │  │
│  │ - /api/calendar/* (school sync, events)                   │  │
│  │ - /api/integrations/* (Gmail, Schoology)                  │  │
│  │ - /api/assistant/chat (general AI assistant)              │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Privacy Layer:                                             │  │
│  │ - privacy_masking.py: Presidio NER + custom regex          │  │
│  │ - llm_privacy_middleware.py: mask ALL prompts before LLM   │  │
│  │ - document_pipeline.py: OCR → classify → mask → UUID       │  │
│  │ - database.py: SecureDocumentDB + EntityMappingDB          │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Multi-Agent System:                                        │  │
│  │ - Orchestrator (QWQ:32B) → routes to specialists          │  │
│  │ - Quant Agent (DeepSeek-R1:32B) → options, Greeks         │  │
│  │ - Life Agent (Llama 3.3:70B) → nutrition, travel          │  │
│  │ - Policy Agent (Mistral:7B) → news, sentiment             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
        ↓                    ↓                    ↓
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  PostgreSQL  │  │  Redis Cache     │  │  Qdrant Vectors  │
│  (10Gi PVC)  │  │  (Session/Queue) │  │  (5Gi PVC)       │
└──────────────┘  └──────────────────┘  └──────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────────┐
│  Ollama (Local LLM Inference)                                    │
│  - Apple Silicon Metal/MPS acceleration                          │
│  - Models: Qwen2.5, DeepSeek-R1, Llama3.3, Mistral, LLaVA     │
│  - Masked input only — raw PII never reaches any model          │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow: Chat with Privacy

```
User Input
    ↓
[1] Privacy Module (Presidio)
    - Detect: PERSON, EMAIL, PHONE, SSN, CREDIT_CARD, MEDICAL_LICENSE, etc.
    - Mask: [PERSON], [EMAIL], [PHONE], [SSN], [CARD], [LICENSE], etc.
    - Log: Audit trail for compliance
    ↓
[2] Embedding Generation
    - Model: sentence-transformers (all-MiniLM-L6-v2)
    - Hardware: CPU/MPS (no GPU required)
    - Output: 384-dim vector
    ↓
[3] Indexing
    - Qdrant: Store vector + masked text metadata
    - MeiliSearch: Index masked text for full-text search
    ↓
[4] Local LLM Inference
    - Ollama: Mistral model
    - Input: Masked text + context from search
    - Output: Streamed response (Server-Sent Events)
    ↓
[5] Optional External LLM (Masked Data Only)
    - Forward masked prompt to OpenAI/Anthropic/Gemini
    - Merge responses
    ↓
[6] Response to User
    - Include: Response text, PII detection flag, sources
    - Never: Original PII/PHI/PCI
```

## Privacy & Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Input Validation                                       │
│ - Rate limiting (per user, per IP)                              │
│ - Input size limits                                             │
│ - Content type validation                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: PII/PHI/PCI Detection & Masking                        │
│ - Presidio Analyzer: Entity detection                           │
│ - Presidio Anonymizer: Masking                                  │
│ - Audit Logging: All masking operations                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Encryption at Rest                                     │
│ - PostgreSQL: Column-level encryption (pgcrypto)               │
│ - Disk-level: EBS encryption (AWS), GCS encryption (GCP)       │
│ - Secrets: K8s Secrets → Vault/AWS Secrets Manager             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Encryption in Transit                                  │
│ - TLS 1.2+ for all external endpoints                           │
│ - mTLS for inter-service communication (optional)               │
│ - Signed API requests (HMAC-SHA256)                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5: Access Control & RBAC                                  │
│ - Kubernetes RBAC: Service account per component               │
│ - Database RLS: Row-level security (Postgres)                  │
│ - API Authentication: JWT tokens                                │
│ - Rate Limiting: Per-user, per-tenant                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 6: Audit Logging & Monitoring                             │
│ - API request logging (all endpoints)                           │
│ - Data access logging (who accessed what, when)                │
│ - PII masking audit trail                                       │
│ - Prometheus metrics + Grafana dashboards                       │
│ - Loki logs aggregation                                         │
│ - Jaeger distributed tracing                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Kubernetes Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                           │
│  Namespace: pla                                                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Deployments (Stateless)                                 │  │
│  │ - frontend (2 replicas, HPA 2-10)                       │  │
│  │ - backend (2 replicas, HPA 2-10)                        │  │
│  │ - redis (1 replica)                                     │  │
│  │ - meili (1 replica)                                     │  │
│  │ - ollama (1 replica, optional)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ StatefulSets (Stateful)                                 │  │
│  │ - postgres (1 replica, PVC 10Gi)                        │  │
│  │ - qdrant (1 replica, PVC 5Gi)                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Services                                                 │  │
│  │ - frontend (LoadBalancer/NodePort 30001)                │  │
│  │ - backend (ClusterIP + NodePort 30000)                  │  │
│  │ - postgres (ClusterIP)                                  │  │
│  │ - redis (ClusterIP)                                     │  │
│  │ - qdrant (ClusterIP + Headless)                         │  │
│  │ - meili (ClusterIP)                                     │  │
│  │ - ollama (ClusterIP)                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ConfigMaps & Secrets                                    │  │
│  │ - postgres-secret (DB credentials)                      │  │
│  │ - google-creds (GCP service account)                    │  │
│  │ - external-llm-keys (API keys)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Ingress                                                 │  │
│  │ - TLS termination (mkcert local, Let's Encrypt cloud)   │  │
│  │ - Route /api → backend                                  │  │
│  │ - Route / → frontend                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Topology

### Local Development (OrbStack on Mac Mini M4)

```
┌─────────────────────────────────────────┐
│  Mac Mini M4 (ARM64)                    │
│  ┌─────────────────────────────────────┐│
│  │ OrbStack (K8s)                      ││
│  │ ┌───────────────────────────────────┐│
│  │ │ pla namespace                     ││
│  │ │ - 8 pods (2 frontend, 2 backend)  ││
│  │ │ - 2 StatefulSets (postgres, qdrant)
│  │ │ - 3 Deployments (redis, meili)    ││
│  │ │ - 1 optional (ollama)             ││
│  │ └───────────────────────────────────┐│
│  │ Storage: Local PVC (10Gi + 5Gi)     ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
```

### Cloud Staging (AWS EKS)

```
┌──────────────────────────────────────────────┐
│  AWS Region (us-east-1)                      │
│  ┌────────────────────────────────────────┐  │
│  │ EKS Cluster (3 nodes, t3.medium)       │  │
│  │ ┌──────────────────────────────────────┐ │
│  │ │ pla namespace                        │ │
│  │ │ - frontend (2-5 replicas, HPA)       │ │
│  │ │ - backend (2-5 replicas, HPA)        │ │
│  │ │ - redis (1 replica)                  │ │
│  │ │ - meili (1 replica)                  │ │
│  │ │ - qdrant (1 replica)                 │ │
│  │ └──────────────────────────────────────┐ │
│  │ Storage: EBS volumes (gp3)             │ │
│  │ Secrets: AWS Secrets Manager           │ │
│  │ Monitoring: CloudWatch + Prometheus    │ │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ RDS Aurora PostgreSQL (Multi-AZ)       │  │
│  │ - Automated backups (35 days)          │  │
│  │ - Read replicas                        │  │
│  │ - Encryption at rest                   │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ ElastiCache Redis (Multi-AZ)           │  │
│  │ - Automatic failover                   │  │
│  │ - Encryption in transit                │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### Cloud Production (Multi-Region)

```
┌─────────────────────────────────────────────────────────────┐
│  Primary Region (us-east-1)                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ EKS Cluster (6 nodes, t3.large)                       │  │
│  │ - frontend (3-10 replicas, HPA)                       │  │
│  │ - backend (3-10 replicas, HPA)                        │  │
│  │ - Qdrant cluster (3 replicas, StatefulSet)            │  │
│  │ - MeiliSearch cluster (2 replicas)                    │  │
│  │ - Redis cluster (3 nodes, Sentinel)                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ RDS Aurora PostgreSQL (Multi-AZ, 3 nodes)             │  │
│  │ - Global database replication                         │  │
│  │ - Automated backups to S3                             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↓ (Global Load Balancer)
┌─────────────────────────────────────────────────────────────┐
│  Secondary Region (eu-west-1)                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ EKS Cluster (read-only replicas)                      │  │
│  │ - frontend (2-5 replicas)                             │  │
│  │ - backend (2-5 replicas, read-only)                   │  │
│  │ - Qdrant read replicas                                │  │
│  │ - Redis read replicas                                 │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ RDS Aurora PostgreSQL (Read replicas)                 │  │
│  │ - Replication lag < 1s                                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Technology Rationale

| Component | Choice | Why |
|-----------|--------|-----|
| Frontend | React + Vite | Fast dev experience, modern DX, small bundle |
| Backend | FastAPI | Async/await, auto-docs, fast, Pythonic |
| Database | PostgreSQL | ACID, JSON support, RLS, mature |
| Cache | Redis | Fast, simple, good for sessions & queues |
| Vector DB | Qdrant | Rust-based, fast, scalable, good API |
| Search | MeiliSearch | Fast, typo-tolerant, easy to operate |
| LLM | Ollama + Mistral | Local, no GPU required, privacy-first |
| Privacy | Presidio | Microsoft-backed, comprehensive entity detection |
| Embeddings | sentence-transformers | Lightweight, CPU-friendly, good quality |
| Container | Docker | Standard, ARM64 support, OrbStack compatible |
| Orchestration | Kubernetes | Industry standard, scales from local to cloud |
| Monitoring | Prometheus + Grafana | Open source, battle-tested, cloud-agnostic |
| Logging | Loki | Lightweight, integrates with Prometheus |
| Tracing | Jaeger | Distributed tracing, good for debugging |

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Chat response | < 2s | Local Ollama inference |
| Search latency | < 100ms | Qdrant vector search |
| API p99 | < 500ms | FastAPI + async |
| Frontend load | < 2s | Vite build, Nginx caching |
| Database query | < 50ms | Indexed queries |
| Uptime | 99.5% | Local: single node, Cloud: multi-AZ |

## Compliance & Certifications

- **HIPAA**: Encryption at rest/transit, audit logging, BAAs with vendors
- **GDPR**: Data portability, right to deletion, consent management
- **SOC2**: Access control, change management, incident response
- **PCI-DSS**: If processing payment cards (not in scope for MVP)

## Privacy-First Document Pipeline

The core innovation: **no raw sensitive data ever reaches an LLM**.

```
┌──────────────────────────────────────────────────────────────────┐
│  Mobile App / Web UI                                             │
│  Camera capture → Base64 encode → POST /api/documents/secure/*  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: OCR Extraction (document_ocr.py)                        │
│  - Primary: Tesseract (pytesseract)                              │
│  - Fallback: LLaVA vision model via Ollama                       │
│  - Supports: JPG, PNG, PDF                                       │
│  - Output: raw text (stays local, never sent externally)         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Step 2: Document Classification (privacy_masking.py)            │
│  - Keyword scoring across 7 categories:                          │
│    finance | health | travel | shopping | legal | personal | other│
│  - Can be overridden by user at upload time                      │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Step 3: Sensitive Entity Detection & Masking                    │
│                                                                  │
│  Phase A — Presidio NER (Microsoft, MIT license)                 │
│    Detects: PERSON, EMAIL, PHONE, SSN, CREDIT_CARD,             │
│             US_BANK_NUMBER, DRIVER_LICENSE, PASSPORT,            │
│             ITIN, IP_ADDRESS, IBAN, MEDICAL_LICENSE,             │
│             DATE_TIME, LOCATION, ORGANIZATION                    │
│                                                                  │
│  Phase B — Custom Regex (privacy_masking.py)                     │
│    Detects: HOSPITAL, MEDICAL_RECORD (MRN), HEALTH_PLAN_ID,     │
│             NPI_NUMBER, DEA_NUMBER, ACCOUNT_NUMBER,              │
│             ROUTING_NUMBER, API_KEY, PASSWORD, ADDRESS            │
│                                                                  │
│  Phase C — Token Replacement                                     │
│    "John Smith SSN 123-45-6789" → "[PERSON_001] SSN [SSN_001]"  │
│                                                                  │
│  Entity Mappings stored locally:                                 │
│    token=[SSN_001], hash=sha256("123-45-6789"),                  │
│    partial="***-**-6789"                                         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Step 4: UUID Assignment & Storage (database.py)                 │
│                                                                  │
│  SecureDocumentDB:                                               │
│    document_uuid, user_uuid, category, masked_text,              │
│    ocr_text_hash (SHA-256), entity_count, status                 │
│                                                                  │
│  EntityMappingDB:                                                │
│    document_uuid, token, entity_type, original_hash,             │
│    partial_reveal, position_start, position_end                  │
│                                                                  │
│  ⚠️  Raw text is NEVER stored. Only SHA-256 hash for integrity.  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Step 5: LLM Analysis (MASKED text only)                         │
│  - Category-specific prompts (finance, health, travel, etc.)     │
│  - Model: Qwen2.5:7b (efficient, runs well on Apple Silicon)    │
│  - Output: JSON { summary, key_findings, action_items }         │
│  - The LLM sees "[PERSON_001]" — never "John Smith"             │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Step 6: Response to Client                                      │
│  {                                                               │
│    "document_uuid": "doc-a1b2c3...",                             │
│    "category": "health",                                         │
│    "masked_text": "[PERSON_001] cholesterol 240 mg/dL...",       │
│    "entity_count": 5,                                            │
│    "analysis": { "summary": "...", "action_items": [...] }       │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
```

### Secure Document API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/documents/secure/upload` | Image → OCR → Mask → UUID → Analyze |
| POST | `/api/documents/secure/text` | Text → Mask → UUID → Analyze |
| POST | `/api/documents/secure/query` | Ask question about a document (masked) |
| GET | `/api/documents/secure/list/{user_uuid}` | List user's documents |
| GET | `/api/documents/secure/{doc_uuid}` | Get document by UUID |
| GET | `/api/documents/privacy/check` | Check if text contains PII |
| GET | `/api/documents/privacy/audit` | Privacy audit log + stats |

### LLM Privacy Middleware (llm_privacy_middleware.py)

```
Any User Content
    ↓
PrivateLLM.generate(prompt)
    ↓
[1] Scan prompt for sensitive data (Presidio + regex)
    ↓
[2] If found → mask all entities before sending
    ↓
[3] Audit log (prompt length, entities masked, model, timestamp)
    ↓
[4] Send MASKED prompt to Ollama (or any LLM)
    ↓
[5] Return response + audit metadata
```

Usage: Replace `OllamaClient` with `PrivateLLM` when processing user content:
```python
from app.services.llm_privacy_middleware import PrivateLLM

llm = PrivateLLM(user_uuid="u-123", role="life")
result = await llm.generate("Analyze John Smith's bank statement...")
# Ollama receives: "Analyze [PERSON_001]'s bank statement..."
```

## Multi-Agent System

```
┌───────────────────────────────────────────────────────────────┐
│  Orchestrator Agent (QWQ:32B)                                  │
│  - Classifies user intent                                      │
│  - Routes to specialist agents                                 │
│  - Merges multi-agent results                                  │
└───────────────────────────────────────────────────────────────┘
         ↓                    ↓                    ↓
┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Quant Agent    │ │  Life Agent      │ │  Policy Agent    │
│  DeepSeek-R1    │ │  Llama 3.3:70B   │ │  Mistral 7B      │
│  32B            │ │                  │ │                  │
│                 │ │  - Nutrition     │ │  - News analysis │
│  - Options      │ │  - Travel        │ │  - Geopolitical  │
│  - Greeks       │ │  - Shopping      │ │  - Sentiment     │
│  - Risk models  │ │  - Wellness      │ │  - Market briefs │
│  - Black-Scholes│ │  - Clean15/Dirty │ │  - Policy shocks │
└─────────────────┘ └──────────────────┘ └──────────────────┘
```

### LLM Model Registry

| Role | Model | Size | Use Case |
|------|-------|------|----------|
| Quant | DeepSeek-R1 | 32B | Options Greeks, risk modeling |
| Orchestrator | QWQ | 32B | Task routing, agentic logic |
| Life | Llama 3.3 | 70B (Q4) | Nutrition, travel, shopping |
| Policy | Mistral | 7B | Fast news, sentiment analysis |
| Document Analysis | Qwen2.5 | 7B | OCR analysis, document Q&A |
| Vision/OCR Fallback | LLaVA | 7B | Image text extraction |
| Email Analysis | Qwen2.5 | 14B | Email parsing, action items |

All models run locally via Ollama on Apple Silicon (Metal/MPS acceleration).

## Future Enhancements

1. **Message Queue**: RabbitMQ/Kafka for async tasks (scraping, embedding)
2. **Worker Pool**: Celery for long-running jobs
3. **Feature Flags**: LaunchDarkly for A/B testing
4. **API Gateway**: Kong or Traefik for rate limiting, auth
5. **Service Mesh**: Istio for advanced networking
6. **GraphQL**: Apollo Server for flexible queries
7. **Mobile**: React Native app for iOS/Android
8. **Offline Mode**: Service Workers + IndexedDB
9. **Real-time**: WebSockets for live updates
10. **ML Pipeline**: Model training for personalization
11. **Encrypted File Storage**: AES-256 encryption for original document images
12. **Database Persistence**: Move entity mappings from in-memory to PostgreSQL
13. **Batch Document Processing**: Queue-based pipeline for bulk uploads

---

**Last Updated**: June 2025
**Version**: 0.2.0
**Status**: Privacy-First Pipeline Operational
