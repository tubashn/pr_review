# ==============================================================================
# PR Review Agent - Production Dockerfile (NVIDIA GPU / CUDA 12.1 + Python 3.11)
# Single Uvicorn worker container for isolated PR code review with Qwen Verifier
# ==============================================================================

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Hugging Face Cache directory configured for persistent volume mount
ENV HF_HOME=/home/appuser/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface

# Install system dependencies (Python 3.11, pip, git, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    git \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set default python3 alias
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch with CUDA 12.1 support
RUN python -m pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Create non-root application user
RUN useradd -m -u 1000 -s /bin/bash appuser \
    && mkdir -p /app /home/appuser/.cache/huggingface /tmp/pr_review \
    && chown -R appuser:appuser /app /home/appuser /tmp/pr_review

WORKDIR /app

# Install Python runtime dependencies
COPY requirements-runtime.txt /app/
RUN python -m pip install --no-cache-dir -r requirements-runtime.txt

# Copy application source code
COPY --chown=appuser:appuser . /app/

# Switch to non-root user
USER appuser

# Expose FastAPI server port
EXPOSE 8000

# Healthcheck using Python stdlib (no external curl dependency required)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1)" || exit 1

# Start FastAPI server with a single worker process (MVP Concurrency Constraint)
CMD ["python", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
