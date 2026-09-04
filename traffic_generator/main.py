"""Traffic Generator Microservice for Legal Agent.

This Cloud Run microservice executes periodic queries against the deployed
legal agent on Agent Runtime / Agent Engine using evaluation questions.
It generates recurring live traffic every 6 hours to feed telemetry,
Cloud Trace, and Gemini Enterprise online evaluation monitors.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
import httpx
from pydantic import BaseModel, Field

# Initialize environment and logging
load_dotenv(find_dotenv())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("traffic_generator")

app = FastAPI(
    title="Legal Agent Traffic Generator",
    version="1.0.0",
    description="Generates synthetic evaluation traffic to drive Agent Runtime telemetry and online evaluation.",
)

# Default Evaluation Questions (matches legal_contracts.evalset.json)
DEFAULT_QUESTIONS: List[str] = [
    (
        "Identify the specific amendment within the Lockheed Martin Corporation "
        "documents that modified the 'Termination' clause. How does the termination date "
        "differ between the original agreement and the currently amended version?"
    ),
    (
        "Based on the original agreement and the subsequent amendments for The Walt Disney "
        "Company, what are the net-new compliance or reporting obligations imposed on the "
        "parties that were entirely absent from the original text?"
    ),
    (
        "Across the entire contract family for UnitedHealth Group Incorporated, list all "
        "counterparties or subsidiaries (such as Optum Services, Inc., or Health Plan of "
        "Nevada, Inc.) that were explicitly added over time."
    ),
    (
        "How was the definition of 'Marketable Securities' modified by the amendments in "
        "the Comcast Corporation family? Quote the original definition and the final "
        "amended definition."
    ),
    (
        "Compare the 'Governing Law' and 'Dispute Resolution' clauses across the Bank of "
        "America and Goldman Sachs documents. Did any of these financial institutions "
        "change their preferred jurisdiction or arbitration rules via an amendment, and "
        "how do their baseline governing laws differ?"
    ),
]


class RunTrafficRequest(BaseModel):
    """Configuration payload for triggering evaluation traffic."""

    reasoning_engine_id: Optional[str] = Field(
        default=None,
        description="Reasoning Engine resource ID. Falls back to REASONING_ENGINE_ID env var.",
    )
    project_id: Optional[str] = Field(
        default=None,
        description="GCP Project ID. Falls back to PROJECT_ID or GOOGLE_CLOUD_PROJECT env var.",
    )
    location: Optional[str] = Field(
        default=None,
        description="Region where Agent Runtime is deployed. Defaults to us-central1.",
    )
    questions: Optional[List[str]] = Field(
        default=None,
        description="Custom list of questions to send. Defaults to standard 5 legal questions.",
    )


class QueryResult(BaseModel):
    """Result of an individual question query."""

    question_index: int
    question: str
    status: str
    latency_seconds: float
    response_length: int
    error_message: Optional[str] = None


class TrafficRunResponse(BaseModel):
    """Summary of traffic run execution."""

    status: str
    started_at: str
    completed_at: str
    total_questions: int
    successful_queries: int
    failed_queries: int
    average_latency_seconds: float
    details: List[QueryResult]


def get_gcp_access_token() -> str:
    """Retrieves Google Cloud OAuth2 access token via Application Default Credentials.

    Returns:
        String access token.
    """
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(GoogleAuthRequest())
    return str(credentials.token)


async def query_deployed_agent(
    client: httpx.AsyncClient,
    access_token: str,
    project_id: str,
    location: str,
    reasoning_engine_id: str,
    question: str,
    question_idx: int,
) -> QueryResult:
    """Sends a query to the deployed Agent Runtime Reasoning Engine.

    Args:
        client: HTTPX asynchronous client.
        access_token: Valid GCP access token.
        project_id: GCP project ID.
        location: GCP region.
        reasoning_engine_id: Deployed Reasoning Engine resource ID.
        question: The legal question prompt.
        question_idx: Question index.

    Returns:
        QueryResult with execution metrics and status.
    """
    endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1beta1/"
        f"projects/{project_id}/locations/{location}/reasoningEngines/"
        f"{reasoning_engine_id}:streamQuery"
    )

    request_payload = {
        "classMethod": "streaming_agent_run_with_events",
        "input": {
            "request_json": json.dumps(
                {
                    "user_id": f"traffic-gen-runner-{question_idx}",
                    "message": {
                        "role": "user",
                        "parts": [{"text": question}],
                    },
                }
            )
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id,
    }

    start_time = time.time()
    try:
        response = await client.post(
            endpoint,
            headers=headers,
            json=request_payload,
            timeout=120.0,
        )
        latency = round(time.time() - start_time, 3)

        if response.status_code == 200:
            resp_bytes = len(response.content)
            logger.info(
                "Query %d succeeded in %.2fs (received %d bytes)",
                question_idx,
                latency,
                resp_bytes,
            )
            return QueryResult(
                question_index=question_idx,
                question=question[:80] + "...",
                status="SUCCESS",
                latency_seconds=latency,
                response_length=resp_bytes,
            )

        error_detail = (
            f"HTTP {response.status_code}: {response.text[:200]}"
        )
        logger.error("Query %d failed: %s", question_idx, error_detail)
        return QueryResult(
            question_index=question_idx,
            question=question[:80] + "...",
            status="FAILED",
            latency_seconds=latency,
            response_length=0,
            error_message=error_detail,
        )

    except Exception as exc:  # pylint: disable=broad-exception-caught
        latency = round(time.time() - start_time, 3)
        logger.error("Exception querying Agent Runtime: %s", exc)
        return QueryResult(
            question_index=question_idx,
            question=question[:80] + "...",
            status="ERROR",
            latency_seconds=latency,
            response_length=0,
            error_message=str(exc),
        )


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for Cloud Run container probes."""
    return {
        "status": "HEALTHY",
        "service": "legal-agent-traffic-generator",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@app.post("/run-eval-traffic", response_model=TrafficRunResponse)
async def run_evaluation_traffic(
    payload: Optional[RunTrafficRequest] = None,
) -> TrafficRunResponse:
    """Executes all evaluation questions against the deployed agent.

    Cloud Scheduler calls this endpoint every 6 hours (0 */6 * * *).
    """
    req = payload or RunTrafficRequest()
    project_id = (
        req.project_id
        or os.getenv("PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    location = req.location or os.getenv("LOCATION", "us-central1")
    engine_id = req.reasoning_engine_id or os.getenv("REASONING_ENGINE_ID")
    questions = req.questions or DEFAULT_QUESTIONS

    if not project_id:
        raise HTTPException(
            status_code=400,
            detail="PROJECT_ID not specified in request body or environment.",
        )

    if not engine_id:
        raise HTTPException(
            status_code=400,
            detail="REASONING_ENGINE_ID not specified in request body or environment.",
        )

    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info(
        "Starting eval traffic run against Reasoning Engine %s in %s (%s)...",
        engine_id,
        location,
        project_id,
    )

    try:
        access_token = get_gcp_access_token()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to obtain GCP access token: {exc}",
        ) from exc

    results: List[QueryResult] = []
    async with httpx.AsyncClient() as client:
        for idx, question in enumerate(questions, start=1):
            res = await query_deployed_agent(
                client=client,
                access_token=access_token,
                project_id=project_id,
                location=location,
                reasoning_engine_id=engine_id,
                question=question,
                question_idx=idx,
            )
            results.append(res)
            # Small pause between questions to simulate realistic user traffic
            await asyncio.sleep(2.0)

    completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    successes = sum(1 for r in results if r.status == "SUCCESS")
    failures = len(results) - successes
    avg_latency = (
        round(sum(r.latency_seconds for r in results) / len(results), 3)
        if results
        else 0.0
    )

    logger.info(
        "Traffic run finished: %d/%d successes, avg_latency=%.2fs",
        successes,
        len(results),
        avg_latency,
    )

    return TrafficRunResponse(
        status="COMPLETED" if failures == 0 else "PARTIALLY_FAILED",
        started_at=started_at,
        completed_at=completed_at,
        total_questions=len(results),
        successful_queries=successes,
        failed_queries=failures,
        average_latency_seconds=avg_latency,
        details=results,
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting traffic generator server on 0.0.0.0:{port}...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

