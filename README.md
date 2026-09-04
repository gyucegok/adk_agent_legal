# Enterprise Legal Analyst Agent

An Enterprise-grade Legal AI Agent built with Google's **Agent Development Kit (ADK)** and managed end-to-end with **`agents-cli`**. The system leverages **Vertex AI RAG Engine 2.0 Serverless Mode** to synthesize, compare, and analyze complex legal contracts, financial schedules, and corporate amendments.

## 🎯 Goal

Demonstrate an end-to-end production-ready agent architecture that eliminates infrastructure overhead by adopting **Serverless RAG 2.0 (`us-central1`)**, standardizes agent operations with **`agents-cli`**, publishes to **Gemini Enterprise**, captures production **OpenTelemetry** traces in **Agent Runtime**, and maintains continuous telemetry via a scheduled **Cloud Run** traffic generator.

🛠️ *Tech: Google ADK, agents-cli, Vertex AI RAG 2.0, Gemini Enterprise, Cloud Run, Cloud Scheduler, OpenTelemetry, FastAPI, Pydantic*

---

## 🏛️ Architecture

![Legal Agent Architecture](images/legal_agent_architecture.png)

1. **Serverless RAG 2.0 (`us-central1`)**: Uses `rag.RagManagedVertexVectorSearch()` to provide zero-cluster vector retrieval over SEC contract filings.
2. **Unified Agent Lifecycle**: Manages local prototyping (`playground`), evaluation, and deployment via `agents-cli`.
3. **Agent Runtime & Telemetry**: Deployed to Google Cloud Agent Runtime with native OpenTelemetry span and log exports visible in the Cloud Console.
4. **Gemini Enterprise Integration**: Registered with Gemini Enterprise application `ge-gyucegok` for web chat and assistant orchestration.
5. **Scheduled Traffic Generator**: Runs as a Cloud Run microservice invoked every 6 hours via Cloud Scheduler to simulate evaluation traffic and maintain live telemetry.

---

## 📂 Key Components & Relevant Documentation

| Component / Folder | Description |
| :--- | :--- |
| **`agent_with_rag/`** | Core ADK agent definition (`App` and `root_agent`) with RAG retrieval tool integration. <br> 🛠️ *Tech: Google ADK, Vertex AI RAG* |
| **`scripts/`** | Python management utilities for RAG 2.0 corpus creation, ingestion, and teardown. <br> 🛠️ *Tech: Vertex AI Python SDK* |
| **`eval/`** | Official Gen AI Evaluation service suite (`EvalTask`, custom pointwise rubrics, and Vertex AI Experiments logging). <br> 🛠️ *Tech: vertexai.evaluation* |
| **`tests/`** | Unit, integration, and `agents-cli` evaluation scenarios (`tests/eval/evalsets/legal_contracts.evalset.json`). <br> 🛠️ *Tech: pytest, agents-cli eval* |
| **`traffic_generator/`** | Containerized FastAPI microservice on Cloud Run scheduled via Cloud Scheduler cron `0 */6 * * *`. <br> 🛠️ *Tech: FastAPI, Uvicorn, Cloud Run, Cloud Scheduler* |
| **`deployment/`** | Infrastructure as Code configuration for single-project and CI/CD targets. <br> 🛠️ *Tech: Terraform* |

---

## ⚙️ Prerequisites

1. **Python**: Version `3.11` or `3.12` installed.
2. **Google Cloud Project**: Active project with billing enabled (`PROJECT_ID="gyucegok-alto"`).
3. **Google Cloud CLI (`gcloud`)**: Installed, authorized, and pointed to your project.
4. **Agent CLI (`agents-cli`)**: Installed via `uv tool install google-agents-cli` or `pip install google-agents-cli`.
5. **Enable Required Google Cloud APIs**:
   ```bash
   gcloud services enable \
       aiplatform.googleapis.com \
       vectorsearch.googleapis.com \
       run.googleapis.com \
       cloudscheduler.googleapis.com \
       agentregistry.googleapis.com
   ```

---

## 🚀 Setup & Installation

### 1. Environment Configuration

Copy the template file to `.env`:

```bash
cp .env.template .env
```

Set the required environment variables in `.env`:

```bash
PROJECT_ID="gyucegok-alto"
LOCATION="us-central1"
GOOGLE_CLOUD_PROJECT="gyucegok-alto"
GOOGLE_CLOUD_LOCATION="us-central1"
GOOGLE_GENAI_USE_VERTEXAI="1"

# OpenTelemetry Instrumentation for Agent Runtime
GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true
OTEL_SEMCONV_STABILITY_OPT_IN="gen_ai_latest_experimental"
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true

# Storage and Corpus Variables
LEGAL_CORPUS="sec-legal-contracts-v2"
LEGAL_SOURCE_GCS_URI="gs://legal-agent-contracts-gyucegok-alto"
```

> [!IMPORTANT]
> Vertex AI RAG Engine 2.0 Serverless Mode backed by Vector Search 2.0 is available **exclusively in `us-central1`**. All deployments, corpora, and services in this repository must use `us-central1`.

### 2. Install Project Dependencies

Install dependencies into your virtual environment:

```bash
pip install -r requirements.txt
```

---

## 🛠️ Helper Scripts

### RAG 2.0 Corpus Management

Use `scripts/manage_rag.py` to automate corpus provisioning and document ingestion:

* **Provision Corpus and Ingest Contracts**:
  ```bash
  python scripts/manage_rag.py setup
  ```
  Creates a serverless corpus using `rag.RagManagedVertexVectorSearch()` and imports all contracts from `LEGAL_SOURCE_GCS_URI`. Prints the resulting `RAG_CORPUS_NAME`.

* **Inspect Corpus Status and File Count**:
  ```bash
  python scripts/manage_rag.py status
  ```

* **Destroy Corpus**:
  ```bash
  python scripts/manage_rag.py destroy
  ```

* **Help and Options**:
  ```bash
  python scripts/manage_rag.py --help
  ```

Backward-compatible shell wrappers are also available:
* `./setup_rag_v2.sh` delegates to `python scripts/manage_rag.py setup`.
* `./destroy_rag.sh` delegates to `python scripts/manage_rag.py destroy`.

---

## 💻 Local Development with `agents-cli`

### Interactive Web Playground
Launch the interactive web UI with hot reloading:
```bash
agents-cli playground
```
Open `http://localhost:8080` in your browser to test multi-turn conversations and inspect retrieved chunks.

### CLI Query Execution
Execute a direct query from the terminal:
```bash
agents-cli run "Compare the 'Governing Law' clauses between Bank of America and Goldman Sachs."
```

### Code Quality & Linting
Validate codebase formatting and typing:
```bash
agents-cli lint
```

---

## 📊 Evaluation & Benchmarking

### Option A: Official Gen AI Evaluation Service
Execute automated rubric grading using the official Vertex AI Gen AI Evaluation Service:

```bash
python eval/run_eval.py
```

* Executes inference across the 5 canonical legal evaluation questions.
* Evaluates answers using custom `PointwiseMetric` rubrics (Clause Override, Net-New Obligations, Entity Tracking, Definition Tracing, and Cross-Family Comparison).
* Logs experiment metrics and parameters directly to **Vertex AI Experiments**.

### Option B: Native `agents-cli` Evaluation Harness
Run the bundled multi-turn evaluation suite:

```bash
agents-cli eval run
```

Uses `tests/eval/eval_config.json` to score `tool_trajectory_avg_score`, `response_match_score`, and `hallucinations_v1`.

---

## ☁️ Deployment & Gemini Enterprise Integration

### 1. Deploy to Agent Runtime
Deploy the packaged agent to Google Cloud Agent Runtime:

```bash
agents-cli deploy
```

The deployed reasoning engine exposes a streaming endpoint:
* **Resource Pattern**: `projects/PROJECT_ID/locations/us-central1/reasoningEngines/ENGINE_ID`
* **Deployed Instance**: `projects/144908374040/locations/us-central1/reasoningEngines/1268560990790746112`

### 2. Inspect Telemetry & Traces
Telemetry is natively enabled via environment variables:
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Navigate to **Agent Platform > Agents > Deployments**.
3. Select the deployed agent.
4. Click **Traces** to view OpenTelemetry spans, latency breakdowns, and tool execution.
5. Click **Logs** to inspect structured execution logs.

### 3. Publish to Gemini Enterprise
Register your deployed agent in your Gemini Enterprise app:

```bash
agents-cli publish gemini-enterprise \
  --agent-runtime-id 1268560990790746112 \
  --gemini-enterprise-app-id ge-gyucegok
```

* **App ID**: `ge-gyucegok` (`ge-gyucegok_1788488839784`)
* **Agent Resource Name**: `projects/144908374040/locations/global/collections/default_collection/engines/ge-gyucegok_1788488839784/assistants/default_assistant/agents/13029818108706916958`

---

## ⏱️ Cloud Run Scheduled Traffic Generator

To generate recurring traffic and supply continuous telemetry to online evaluation monitors, deploy the containerized traffic generator microservice:

```bash
cd traffic_generator
./deploy_traffic_generator.sh
```

### What `deploy_traffic_generator.sh` Configures:
1. **API Enablement**: Enables `run.googleapis.com` and `cloudscheduler.googleapis.com`.
2. **Dedicated Service Account**: Provisions `legal-traffic-scheduler-sa` with `roles/aiplatform.user` and `roles/logging.logWriter`.
3. **Cloud Run Deployment**: Deploys the microservice with port `8080` in `us-central1` (`https://legal-agent-traffic-gen-ox6qvewbia-uc.a.run.app`).
4. **IAM Invocations**: Grants the service account `roles/run.invoker` on the Cloud Run service.
5. **Cloud Scheduler Job**: Configures job `legal-agent-eval-traffic-cron` running on schedule `0 */6 * * *` (every 6 hours) targeting `/run-eval-traffic` with OIDC authentication.

### Manual Traffic Trigger
Trigger a traffic run manually using cURL:

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://legal-agent-traffic-gen-ox6qvewbia-uc.a.run.app/run-eval-traffic
```

Check microservice health:
```bash
curl -X GET \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://legal-agent-traffic-gen-ox6qvewbia-uc.a.run.app/health
```

---

## 🧹 Teardown & Resource Cleanup

To delete the RAG 2.0 corpus and Cloud Run services:

```bash
# Delete RAG corpus
python scripts/manage_rag.py destroy

# Delete Cloud Run service and scheduler job
gcloud run services delete legal-agent-traffic-gen --region=us-central1 --quiet
gcloud scheduler jobs delete legal-agent-eval-traffic-cron --location=us-central1 --quiet
```
