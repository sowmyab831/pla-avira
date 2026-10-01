# Multi-stage build for Python application
ARG TARGETARCH
FROM --platform=linux/${TARGETARCH:-arm64} python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY pyproject.toml .

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 sqlalchemy==2.0.23 \
    asyncpg==0.29.0 redis==5.0.1 httpx==0.25.2 pydantic==2.5.0 \
    pydantic-settings==2.1.0 python-multipart==0.0.6 python-dotenv==1.0.0 \
    aiofiles==23.2.1 presidio-analyzer==2.2.35 presidio-anonymizer==2.2.35 \
    sentence-transformers==2.7.0 numpy==1.24.3 pandas==2.1.3 \
    pdfplumber==0.10.3 requests==2.31.0 qdrant-client==1.6.9 \
    meilisearch==0.27.0 minio==7.2.0 spacy==3.8.0 \
    anthropic==0.7.1 openai==1.3.5 google-auth-oauthlib>=1.0.0 \
    google-auth>=2.0.0 google-api-python-client aiohttp==3.9.1 \
    beautifulsoup4==4.12.2 bcrypt==4.1.2 PyJWT==2.8.0 \
    email-validator==2.1.0 yfinance scikit-learn pytesseract \
    pillow greenlet torch torchvision torchaudio transformers \
    pdf2image cryptography xgboost==3.0.* lxml

# Final stage
ARG TARGETARCH
FROM --platform=linux/${TARGETARCH:-arm64} python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    tesseract-ocr \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Download spaCy model at build time (avoids startup delays)
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m spacy download en_core_web_lg

# Install libgomp (needed by xgboost) in the final stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY app/ ./app/

# Copy trained XGBoost models so /api/forecast can apply the ML tilt in K8s.
# Build context for this image is `backend/`, so we use a relative path back
# up via .dockerignore exception — see scripts/avira-redeploy-backend.sh which
# stages models into backend/_models_staged before docker build.
COPY _models_staged/ /app/meridian/research/models/
ENV AVIRA_MODELS_DIR=/app/meridian/research/models

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# GPU/CUDA environment variables
ENV CUDA_VISIBLE_DEVICES=0
ENV TORCH_HOME=/tmp/torch_cache
ENV TRANSFORMERS_CACHE=/tmp/transformers_cache

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
