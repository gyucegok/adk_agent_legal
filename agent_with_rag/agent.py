"""Enterprise Legal Analyst Agent definition.

This module defines the ADK root agent and App powered by Vertex AI
RAG 2.0 Serverless mode (RagManagedVertexVectorSearch in us-central1).
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.apps.app import App
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
import vertexai
from vertexai.preview import rag

# Load environment configuration
load_dotenv(find_dotenv())

PROJECT_ID: Optional[str] = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION: str = os.getenv("LOCATION", "us-central1")
LEGAL_CORPUS_DISPLAY_NAME: str = os.getenv("LEGAL_CORPUS", "sec-legal-contracts-v2")
RAG_CORPUS_NAME: Optional[str] = os.getenv("RAG_CORPUS_NAME")
AGENT_MODEL: str = (
    os.getenv("AGENT_MODEL")
    or os.getenv("MODEL_NAME")
    or os.getenv("MODEL")
    or "gemini-3.7-flash"
)

# Initialize Vertex AI in us-central1 for RAG 2.0 Serverless support
if PROJECT_ID:
    vertexai.init(project=PROJECT_ID, location=LOCATION)

# Build RAG Retrieval Tool
tools = []
if RAG_CORPUS_NAME:
    ask_vertex_retrieval = VertexAiRagRetrieval(
        name="retrieve_rag_documentation",
        description=(
            "Use this tool to retrieve legal contracts and documentation from the RAG corpus. "
            "You MUST use this tool to answer ANY question regarding contracts, amendments, covenants, or counterparties."
        ),
        rag_resources=[
            rag.RagResource(
                rag_corpus=RAG_CORPUS_NAME
            )
        ],
        similarity_top_k=45,
        vector_distance_threshold=0.5,
    )
    tools.append(ask_vertex_retrieval)

LEGAL_ANALYST_INSTRUCTION = """You are an expert legal analyst assisting corporate counsel with contract synthesis.
Synthesize the best possible answer using the provided context from the RAG corpus.
If parts of the answer are missing from the context, explicitly state what is missing, but still provide the information you *do* have rather than refusing to answer entirely. Do NOT hallucinate.

Here are examples of how you should structure your answers:

Example 1 (Entity Additions):
Question: Across the contract family for Acme Corp, list all counterparties or subsidiaries that were explicitly added over time.
Answer: Based on the provided documents, the following entities were explicitly added:
- Acme Tech LLC was added as a guarantor in the First Amendment.
- Acme Global Inc. was added in the Second Amendment.
Information missing: The documents do not list any entities that were removed.

Example 2 (Clause Overrides):
Question: Identify the specific amendment within the Beta Corp documents that modified the 'Termination' clause. How does the termination date differ?
Answer: The 'Termination' clause was modified by Amendment No. 3. The amended termination date is December 31, 2026.
Information missing: The original agreement containing the original termination date is not present in the provided context, so the exact difference cannot be calculated.

Example 3 (Cross-Family Comparison):
Question: Compare the 'Governing Law' clauses across Gamma Inc and Delta LLC. Did any change their preferred jurisdiction?
Answer: 
- Gamma Inc: The baseline governing law is New York. Amendment 2 shifted the jurisdiction to binding arbitration in Delaware.
- Delta LLC: The governing law is California. No amendments were found that shifted this jurisdiction."""

# Define root_agent for ADK and agents-cli
root_agent = Agent(
    name="legal_analyst_agent",
    model=AGENT_MODEL,
    tools=tools,
    instruction=LEGAL_ANALYST_INSTRUCTION,
)

# Standard App pattern for ADK 2.0 and Gemini Enterprise Agent Platform
app = App(
    name="legal_agent",
    root_agent=root_agent,
)
