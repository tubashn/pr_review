# PR Review - AI Pull Request Review Agent

![CI](https://github.com/tubashn/pr_review/actions/workflows/ci.yml/badge.svg)

AI ve deterministic static analysis kullanarak Pull Request'leri analiz eden deneysel code review sistemi.

## Current Architecture

```
Pull Request
→ Diff + Code Context
→ Qwen Correctness / Security / Maintainability Reviewers
+ PMD
→ Candidate Findings
→ Hierarchical Finding Verifier (AST + Grounding Strategy + Qwen 7B)
→ Merge / Deduplicate
→ Fix Agent V1 (Eligibility Gate -> Patch Generation -> Safety Validation)
→ Final Report & GitHub Summary Comment
```

## Current Status

### Completed
* PR diff extraction
* code context extraction
* isolated branch/worktree scanning
* PMD baseline + diff analysis
* 3 specialized Qwen reviewers
* held-out PR test set
* automatic precision/recall/F1 evaluation
* Qwen 1.5B / 7B / 14B experiments
* QLoRA dataset pipeline
* 48 scenarios / 144 samples
* QLoRA pilot training
* AI verifier prompt/benchmark/evaluator
* Base Qwen 7B verifier inference & hierarchical verification
* FastAPI REST API Server with singleton model caching
* GitHub Webhook integration with HMAC SHA-256 and idempotency
* GitHub Pull Request summary comment publishing
* Docker containerization with GPU support and volume caching
* Deterministic mock backend for local dev and CI
* GitHub Actions CI pipeline
* Fix Agent V1 (Conservative automated patch suggestions)

### Planned
* Maven test regression verification in PR pipeline
* Automatic email delivery

---

## Run the MVP (End-to-End Execution)

Tam uçtan uca PR review akışını çalıştırmak için `run_pr_review.py` runner'ını kullanabilirsiniz:

### 1. Mock / Dry-Run Modu (Hızlı Test)
```bash
python run_pr_review.py --repo <target-repo-path> --branch <pr-branch> --dry-run
```

### 2. Qwen2.5-Coder-7B (4-Bit NF4 / GPU)
```bash
python run_pr_review.py \
  --repo <target-repo-path> \
  --branch <pr-branch> \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --backend transformers \
  --quantization 4bit \
  --output pr_review_report.json
```

### 3. OpenAI-Compatible API Modu (vLLM / Ollama / Remote Endpoint)
```bash
python run_pr_review.py \
  --repo <target-repo-path> \
  --branch <pr-branch> \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --backend openai \
  --api-base http://localhost:8000/v1 \
  --output pr_review_report.json
```

---

## Run as API Service (FastAPI Server)

PR Review Agent'ı bir REST API mikroservisi olarak çalıştırmak için:

### 1. Servisi Başlatma
```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### 2. Health Check
* **Endpoint**: `GET http://localhost:8000/health`
* **Swagger UI / OpenAPI**: `http://localhost:8000/docs`

### 3. Review İsteği Gönderme

#### cURL:
```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "C:\\path\\to\\orderapp-server",
    "branch": "tuba-test-hardcoded-secret",
    "base": "main",
    "pmd": false
  }'
```

#### Windows PowerShell:
```powershell
$body = @{
    repo = "C:\path\to\orderapp-server"
    branch = "tuba-test-hardcoded-secret"
    base = "main"
    pmd = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/review" -Method Post -Body $body -ContentType "application/json"
```

---

## GitHub Webhook Ingestion (`/webhook/github`)

PR Review Agent, GitHub Pull Request eventlerini kabul ederek otomatik kod incelemesi başlatabilen güvenli bir webhook altyapısına sahiptir.

### 1. Environment Değişkenleri
* `GITHUB_WEBHOOK_SECRET`: GitHub Webhook HMAC SHA-256 secret anahtarı. Tanımlıysa gelen isteklerin `X-Hub-Signature-256` imzası doğrulanır.
* `GITHUB_ALLOWED_REPOS`: Virgülle ayrılmış izinli repo listesi (Örn: `owner/repo1,owner/repo2`). Tanımlıysa liste dışındaki istekler 403 Forbidden ile reddedilir.
* `GITHUB_TOKEN`: Private repository'ler için git fetch/clone erişim token'ı.

### 2. Webhook ve Comment Publishing Akışı
```
GitHub PR Event (opened / reopened / synchronize)
  │
  ├── [1] POST /webhook/github
  ├── [2] HMAC SHA-256 Signature Verification (Constant-time comparison)
  ├── [3] Action & Event Filtering (pull_request: opened, reopened, synchronize)
  ├── [4] Repository Allowlist Enforcement (GITHUB_ALLOWED_REPOS)
  ├── [5] Idempotency Check (<repo>#<pr>@<head_sha>)
  │         ├── Processing / Completed -> 200 OK (Duplicate, skipped)
  │         └── New / Failed -> 202 Accepted (Background review scheduled)
  │
  ├── [6] Background Execution (Isolated temporary clone + run_review pipeline)
  │
  └── [7] GitHub Comment Publishing (Single Summary Bot Comment)
            ├── Existing bot comment search (via <!-- pr-review-agent --> marker)
            ├── Found -> PATCH /issues/comments/{comment_id} (Update existing)
            └── Not found -> POST /issues/{pr}/comments (Create new)
```

> **Not:** Sistem PR thread'ini doldurmamak adına tek bir özet bot yorumu (Single Summary Comment) oluşturur veya günceller. Şimdilik satır içi (inline) file review comments eklenmemiştir.

### 3. Review Durumu Sorgulama
* **Endpoint**: `GET /webhook/reviews/{review_key}` veya `GET /webhook/status?review_key=<key>`
* **Örnek Key**: `owner/repo#42@a1b2c3d4e5f6...`
* **Dönen Bilgiler**: `status` (processing, completed, failed), `candidate_count`, `verified_findings_count`, `rejected_findings_count`, `comment_publish_status`.

---

## Docker Deployment (GPU Supported)

PR Review Agent, Google Colab'dan bağımsız olarak NVIDIA GPU barındıran herhangi bir Linux sunucuda Docker container olarak çalıştırılabilir.

### 1. Host Gereksinimleri
* **NVIDIA GPU Driver** (CUDA 12.1+ uyumlu)
* **Docker Engine** & **Docker Compose**
* **NVIDIA Container Toolkit** (`nvidia-container-toolkit`)

Host GPU erişimini doğrulamak için:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
```

### 2. Ortam Değişkenleri Hazırlığı
`.env.example` dosyasını `.env` olarak kopyalayın ve GitHub token/secret bilgilerinizi girin:
```bash
cp .env.example .env
```

### 3. Container'ı Başlatma
```bash
# Arka planda başlat ve build et
docker compose up -d --build

# Logları canlı takip et
docker compose logs -f

# Durdurma
docker compose down
```

### 4. Health Check & GPU Doğrulama
```bash
curl http://localhost:8000/health
```
Response örneği:
```json
{
  "status": "ok",
  "service": "pr-review-agent",
  "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "backend": "transformers",
  "quantization": "4bit",
  "model_loaded": false,
  "webhook_enabled": true,
  "gpu_available": true,
  "gpu_device": "Tesla T4"
}
```

### 5. Model Ağırlıkları ve Cache Davranışı
* **Ağırlıklar image içine gömülmez**: Docker build süresi hızlıdır ve image boyutu küçüktür.
* **Kalıcı Volume (`pr_review_hf_model_cache`)**: İlk semantik inceleme sırasında indirilen Qwen model ağırlıkları host üzerindeki Docker volume'unda saklanır; container yeniden başlatıldığında tekrar indirilmez.
* **In-Memory Singleton (`MODEL_CACHE`)**: Container çalışırken model GPU belleğinde kalıcı tutulur ve sonraki isteklerde doğrudan kullanılır.
* **Lazy-Loading**: Clean PR'larda (0 candidate) GPU modeli hiç belleğe yüklenmez.

### 6. Tekil Worker Kısıtı (MVP Concurrency Constraint)
> ⚠️ **Önemli Mimari Not:** Servis; GPU bellek çakışmasını önlemek için `INFERENCE_LOCK`, model önbellekleme için `MODEL_CACHE` ve mükerrer review'ları engellemek için process-local `IDEMPOTENCY_STORE` kullanır. Bu nedenle container **tek bir Uvicorn worker process** (`--workers 1`) ile çalışmalıdır. Yatay ölçekleme (horizontal scaling) öncesinde idempotency store ve iş kuyruğu Redis/PostgreSQL gibi paylaşımlı bir altyapıya taşınmalıdır.

### 7. Production HTTPS & Reverse Proxy Notu
Cloudflare quick tunnel (`cloudflared tunnel --url ...`) veya ngrok yalnızca yerel test ve geçici demolar içindir. Production ortamında GitHub Webhook'ları için kalıcı bir alan adı (domain) arkasında Nginx/Caddy reverse proxy ve geçerli SSL/TLS sertifikası kullanılmalıdır.

---

## Local Development Without GPU (Mock Backend)

Laptop veya GPU bulunmayan ortamlarda ürün akışlarını (FastAPI, Webhook, HMAC doğrulama, Idempotency, GitHub Comment güncelleme) test etmek için **Mock Backend** (`PR_REVIEW_BACKEND=mock`) kullanılır.

### 1. Mimari Mod Ayrımı
| Özellik | Local / CI Development | Real Model Deployment |
|---|---|---|
| **Ortam** | Laptop / CPU Sunucu / CI Runner | NVIDIA GPU Sunucu (CUDA 12.1+) |
| **Backend** | `PR_REVIEW_BACKEND=mock` | `PR_REVIEW_BACKEND=transformers` |
| **Model** | Mock Verifier (İndirme YOK) | `Qwen/Qwen2.5-Coder-7B-Instruct` |
| **Amaç** | Webhook, API, Idempotency, Comment entegrasyonu | Gerçek semantik kod analizi ve doğruluk |

> ℹ️ **Not:** Mock backend model doğruluğunu ölçmek için kullanılmaz; yalnızca uçtan uca ürün ve entegrasyon geliştirme içindir.

### 2. GPU'suz Docker Container Çalıştırma
```bash
# GPU rezervasyonu ve model indirmesi olmadan başlat
docker compose -f docker-compose.dev.yml up -d --build

# Health kontrolü (backend: mock, model_loaded: false)
curl http://localhost:8000/health
```

### 3. Local Python ile Çalıştırma
```bash
# Ortam değişkenlerini ayarla
export PR_REVIEW_BACKEND=mock
export PR_REVIEW_DEVICE=cpu

# Sunucuyu başlat
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 1
```

### 4. Mock Review İsteği Örneği
```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "C:\\path\\to\\orderapp-server",
    "branch": "tuba-test-hardcoded-secret",
    "base": "main",
    "pmd": false
  }'
```

---

## Continuous Integration (GitHub Actions)

Projede `main` branch'ine yapılan her push ve pull request için otomatik GitHub Actions CI workflow'u (`.github/workflows/ci.yml`) çalışır.

* **GPU Gerektirmez**: GitHub-hosted `ubuntu-latest` runner üzerinde `PR_REVIEW_BACKEND=mock` ile çalışır.
* **Model İndirmesi Yapmaz**: `HF_HUB_OFFLINE=1` ve `TRANSFORMERS_OFFLINE=1` tanımlıdır; hiçbir LLM ağırlığı indirilmez.
* **Kapsam**:
  1. Python syntax & bytecode compilation check (`compileall`)
  2. Core PR Review MVP & FastAPI server testleri (`test_pr_review_mvp.py`, `test_api_server.py`)
  3. Deterministic Mock Backend testleri (`test_mock_backend.py`)
  4. GitHub Webhook HMAC & Comment Client testleri (`test_webhook.py`, `test_github_client.py`)
  5. Docker konfigürasyon & .dockerignore denetim testleri (`test_docker_setup.py`)
  6. Bakeoff framework testleri (`test_bakeoff_framework.py`)
  7. Benchmark V2 veri seti ve semantik denetim testleri (`validate_benchmark.py`, `ci_audit_runner.py`)
* **Gerçek LLM / GPU Doğrulamaları**: Model kalite ve doğruluk bake-off testleri CI pipeline'ı dışında, özel GPU ortamlarında (Colab / Linux GPU sunucusu) yürütülür.
* **Docker Build Politikası**: Full CUDA Docker build süresi uzun olduğundan CI aşamasında `test_docker_setup.py` ile statik konfigürasyon denetlenir; üretim CUDA image build işlemi deployment aşamasında yapılır.

---

## Fix Agent V1 (Automated Patch Suggestions)

PR Review Agent, verifier tarafından `ACCEPT` edilmiş belirli finding'ler için kullanıcıya manuel inceleme gerektiren, güvenli ve konservatif **unified diff patch önerileri** üretir.

### 1. Güvenlik ve Kapsam Kuralları
* **Asla Target Repo'yu Mutate Etmez**: `git apply`, branch write veya commit/push işlemleri yapmaz.
* **Deterministic Eligibility Gate (`fix_eligibility.py`)**:
  - Yalnızca verifier tarafından onaylanan (`decision == ACCEPT`) finding'leri işler.
  - Sadece `correctness_logic` ve `maintainability` kategorilerini kabul eder.
  - **Güvenlik finding'leri (`security_validation`) otomatik düzeltilmez** (`security_findings_not_auto_fixed`).
  - **Absence/eksik kod finding'leri otomatik düzeltilmez** (`absence_type_not_auto_fixed`).
  - Çoklu dosya (`multi_file_not_supported`) veya geçersiz dosya tipleri reddedilir.
* **Deterministic Patch Safety Validator (`patch_validator.py`)**:
  - Standart unified diff formatı (`--- a/...`, `+++ b/...`, `@@ ... @@`) zorunludur.
  - Sadece finding'in ait olduğu tekil dosyayı değiştirebilir; path traversal (`..`) ve mutlak sistem yolları reddedilir.
  - **Maksimum 20 Değişen Satır Limiti**: Eklenen + silinen kaynak satır sayısı 20'yi aşarsa patch `patch_too_large` olarak reddedilir.
  - Dosya oluşturma, silme, yeniden adlandırma veya binary patch işlemleri engellenir.
  - AST Sanity: Geçici uygulanan patch üzerinde parantez/süslü parantez dengesi ve Java token geçerliliği kontrol edilir.

### 2. Kullanım & Konfigürasyon
Fix Agent varsayılan olarak **KAPALIDIR** (`PR_REVIEW_FIX_AGENT_ENABLED=false`).

* **Environment**: `PR_REVIEW_FIX_AGENT_ENABLED=true`
* **CLI**: `python run_pr_review.py --repo <path> --branch <branch> --suggest-fixes`
* **API**: `POST /review` body'sinde `"suggest_fixes": true`
* **GitHub Summary Comment**: Fix Agent aktif olduğunda geçerli öneriler `### 💡 Suggested Fixes` başlığı altında diff bloğu olarak özet yoruma eklenir.

---

## Fix Agent Evaluation Harness (`evaluation/fix_agent_v1/`)

Fix Agent V1'in patch güvenliğini, uygulama başarısını ve beklenen kod durumuna uygunluğunu (ground-truth match) ölçmek için bağımsız, sentetik ve deterministik bir değerlendirme altyapısıdır.

### 1. Değerlendirme Pipeline'ı
```
Synthetic Verified Finding
  │
  ├── [1] Fix Agent V1 (fix_agent.py)
  ├── [2] Unified Diff Generation
  ├── [3] Patch Safety Validation (patch_validator.py)
  ├── [4] In-Memory Temporary Apply (apply_unified_diff_to_text)
  ├── [5] Expected Source Comparison (Normalized Whitespace)
  └── [6] Metrics & Failure Taxonomy Aggregation
```

### 2. Neyi Ölçer ve Neyi Ölçmez?
* **Neyi Ölçer?**:
  - **Patch Güvenliği**: Sadece hedeflenen dosyanın değişmesi, path traversal engellenmesi, <= 20 satır sınırı.
  - **Uygulanabilirlik**: Üretilen patch'in kaynak koda hatasız uygulanabilmesi.
  - **Ground-Truth Doğruluğu**: Uygulanan kodun `expected_after.java` ile tam eşleşmesi.
  - **Minimallik / Over-edit**: Gerekli satırlar dışında fazladan kod değiştirilip değiştirilmediği.
  - **Güvenli Skip Oranı**: Güvenlik ve eksik kod gibi kapsam dışı senaryoların güvenle atlanması.
* **Neyi Ölçmez?**:
  - Tam proje Maven/Gradle derleme süreci (javac/classpath).
  - Maven unit/entegrasyon test regresyonları.
  - Runtime uygulama davranış garantisi.
  *(Bu kontroller ilerideki sandbox/build-and-test aşamalarında ele alınacaktır.)*

### 3. Dataset İstatistikleri ve HOLDOUT İzolasyonu
* **Toplam Senaryo**: 30 sentetik Java senaryosu
* **DEV Split**: 22 senaryo (15 Eligible, 7 Ineligible)
* **HOLDOUT Split**: 8 senaryo (5 Eligible, 3 Ineligible)

> 🔒 **HOLDOUT İzolasyon Kuralı**: `HOLDOUT` split'i yalnızca nihai one-shot değerlendirme içindir. Prompt düzenlemeleri, eligibility kural tuning'i veya mock kuralları için **asla kullanılmamalıdır**.

### 4. Çalıştırma Komutları
```bash
# 1. Dataset Doğrulama ve Audit
python evaluation/fix_agent_v1/validate_fix_eval.py
python evaluation/fix_agent_v1/audit_fix_eval.py
python evaluation/fix_agent_v1/test_fix_eval_framework.py

# 2. Mock DEV Evaluation (Hızlı / GPU-Free)
python evaluation/fix_agent_v1/run_fix_eval.py --split DEV --backend mock
python evaluation/fix_agent_v1/evaluate_fix_results.py evaluation/fix_agent_v1/results/mock_dev.json

# 3. Real Model Evaluation on GPU (Tesla T4 / Colab / Linux GPU)
python evaluation/fix_agent_v1/run_fix_eval.py \
  --split DEV \
  --backend transformers \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --quantization 4bit \
  --output evaluation/fix_agent_v1/results/qwen7b_dev.json

python evaluation/fix_agent_v1/evaluate_fix_results.py evaluation/fix_agent_v1/results/qwen7b_dev.json
```