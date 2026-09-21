# Google Cloud Platform (GCP) Deployment Guide

This document records the end-to-end architecture, provisioning, deployment procedure, and verification steps for the **Legal Analyst Agent** on Google Cloud Platform, authored from the perspective of an implementation and deployment engineer.

---

## 1. Architectural Overview & Rationale

The solution combines three specialized Google Cloud managed services into an enterprise agent pipeline:

```
┌────────────────────────────────────────────────────────┐
│ Cloud Scheduler (Traffic Generator Cron, every 45m)    │
└──────────────────────────┬─────────────────────────────┘
                           │ OIDC Token
                           ▼
┌────────────────────────────────────────────────────────┐
│ Cloud Run Service (Traffic Generator Microservice)     │
│ Region: us-central1                                    │
└──────────────────────────┬─────────────────────────────┘
                           │ ADC / Vertex AI streamQuery API
                           ▼
┌────────────────────────────────────────────────────────┐
│ Gemini Enterprise Agent Runtime (Reasoning Engine)      │
│ Region: us-central1 (ID: 1268560990790746112)          │
│ Engine Runtime: google-adk (OpenTelemetry Tracing)     │
│ Environment: GOOGLE_CLOUD_LOCATION="global"             │
│ Model: gemini-3.8-flash                                │
└──────────────────────────┬─────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│ Gemini 3.8 Flash         │  │ Vertex AI RAG 2.0        │
│ Endpoint: global         │  │ Serverless Vector Search │
│ Model: gemini-3.8-flash  │  │ Region: us-central1       │
└──────────────────────────┘  └──────────────────────────┘
```

### Architectural Rationale:
1. **Gemini Enterprise Agent Runtime (Vertex AI Reasoning Engine)**:
   - Provides serverless, managed execution of the Google Agent Development Kit (ADK) agent with built-in Cloud Logging and Cloud Trace OpenTelemetry telemetry.
   - Hosted in `us-central1` alongside the Vertex AI RAG corpus.

2. **Model Endpoint Location (`GOOGLE_CLOUD_LOCATION="global"`)**:
   - Modern Gemini publisher models (including `gemini-3.8-flash` and `gemini-3.7-flash`) are deployed via Vertex AI's global publisher model endpoint (`projects/{PROJECT_ID}/locations/global/publishers/google/models/...`).
   - If regional endpoints such as `us-central1` are targeted for the model call, Vertex AI returns `404 NOT_FOUND: Publisher model ... was not found`.
   - By setting `GOOGLE_CLOUD_LOCATION="global"` while keeping `LOCATION="us-central1"` for the RAG corpus, the agent successfully routes inference requests to the global model pool while accessing RAG resources in `us-central1`.

3. **Vertex AI RAG 2.0 Serverless Mode**:
   - RAG 2.0 Serverless backed by Vector Search 2.0 is deployed in `us-central1` with automatic chunking and embedding generation.
   - Corrupted or unneeded infrastructure is avoided; the corpus is indexed directly from Google Cloud Storage (`gs://legal-agent-contracts-gyucegok-alto`).

4. **Cloud Run Synthetic Traffic Generator**:
   - Deployed as a containerized FastAPI service on Cloud Run in `us-central1`.
   - Invoked every 45 minutes via Cloud Scheduler with IAM OIDC authentication.
   - Runs a balanced matrix of healthy legal reasoning queries, complex cross-contract comparisons, and deliberate fault-injection scenarios to validate agent telemetry, error metrics, and span logs in Cloud Logging.

---

## 2. Infrastructure & Resource Inventory

| Resource | Service / Type | Resource ID / Identifier | Region |
|---|---|---|---|
| Project | Google Cloud Project | `gyucegok-alto` | `global` |
| Agent Runtime | Vertex AI Reasoning Engine | `1268560990790746112` | `us-central1` |
| RAG Corpus | Vertex AI RAG Engine 2.0 | `projects/144908374040/locations/us-central1/ragCorpora/6217527148840747008` | `us-central1` |
| Contracts Bucket | Cloud Storage | `gs://legal-agent-contracts-gyucegok-alto` | `us-central1` |
| Traffic Generator | Cloud Run | `legal-agent-traffic-gen-ox6qvewbia-uc.a.run.app` | `us-central1` |
| Traffic Trigger | Cloud Scheduler | `legal-agent-traffic-scheduler` (`*/45 * * * *`) | `us-central1` |
| Foundation Model | Vertex AI Model Garden | `gemini-3.8-flash` | `global` |

---

## 3. Step-by-Step Deployment Procedure

### Step 1: Configure Environment Variables
Prepare the deployment environment in `.env`:
```bash
PROJECT_ID="gyucegok-alto"
LOCATION="us-central1"
GOOGLE_CLOUD_PROJECT="gyucegok-alto"
GOOGLE_CLOUD_LOCATION="global"
GOOGLE_GENAI_USE_VERTEXAI="1"

# Agent Model Configuration
AGENT_MODEL="gemini-3.8-flash"
EVAL_JUDGE_MODEL="gemini-3.8-flash"

# Telemetry
GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true
OTEL_SEMCONV_STABILITY_OPT_IN="gen_ai_latest_experimental"
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true

# RAG Configuration
LEGAL_CORPUS="sec-legal-contracts-v2"
LEGAL_SOURCE_GCS_URI="gs://legal-agent-contracts-gyucegok-alto"
RAG_CORPUS_NAME="projects/144908374040/locations/us-central1/ragCorpora/6217527148840747008"
REASONING_ENGINE_ID="1268560990790746112"
TRAFFIC_SCHEDULE_CRON="*/45 * * * *"
```

### Step 2: Deploy to Gemini Enterprise Agent Runtime
Deploy the ADK agent using `agents-cli`:
```bash
agents-cli deploy \
  --project gyucegok-alto \
  --no-confirm-project \
  --update-env-vars="GOOGLE_CLOUD_LOCATION=global,AGENT_MODEL=gemini-3.8-flash"
```

The CLI packages the local `agent_with_rag/` source and requirements, builds the container image in Artifact Registry, and creates or updates the Reasoning Engine resource.

### Step 3: Deploy Synthetic Traffic Generator to Cloud Run
Deploy the traffic generator container and schedule:
```bash
cd traffic_generator
./deploy_traffic_generator.sh
```
This script:
1. Builds and deploys the Cloud Run service in `us-central1`.
2. Creates the `legal-agent-traffic-invoker` service account.
3. Sets up Cloud Scheduler with a cron schedule (`*/45 * * * *`) targeting `/execute-traffic`.

---

## 4. Verification & Testing

### Live Agent Query Verification
Verify that the deployed Reasoning Engine responds successfully without 404 or authorization errors:
```python
import json, requests, google.auth
from google.auth.transport.requests import Request

credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
credentials.refresh(Request())

endpoint = "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/gyucegok-alto/locations/us-central1/reasoningEngines/1268560990790746112:streamQuery"
headers = {
    "Authorization": f"Bearer {credentials.token}",
    "Content-Type": "application/json",
    "X-Goog-User-Project": "gyucegok-alto",
}
payload = {
    "classMethod": "streaming_agent_run_with_events",
    "input": {
        "request_json": json.dumps({
            "user_id": "verification-user",
            "message": {
                "role": "user",
                "parts": [{"text": "Identify the termination date under Amendment No. 2 to the Lockheed Martin Revolving Credit Agreement."}],
            },
        })
    },
}

response = requests.post(endpoint, headers=headers, json=payload, stream=True)
assert response.status_code == 200
```

**Verification Result**:
- HTTP Status: `200 OK`
- Model Version: `gemini-3.8-flash`
- Output:
  > *"Under Amendment No. 2 (dated as of August 28, 2025) to the Lockheed Martin Revolving Credit Agreement, the extended **Commitment Termination Date** is **August 24, 2030** (extended from August 24, 2029)."*
- RAG retrieval and synthesis verified working end-to-end.
