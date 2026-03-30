from google.adk.agents.llm_agent import Agent
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
import vertexai
from vertexai.preview import rag
import os
from dotenv import load_dotenv, find_dotenv

# Load .env from the same directory as this script
load_dotenv(find_dotenv())
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
LEGAL_CORPUS = os.environ.get("LEGAL_CORPUS", "sec-legal-contracts")

vertexai.init(project=PROJECT_ID, location=LOCATION)

# In Agent Engine, dynamic API calls at import time can fail or timeout.
# We expect the corpus name to be injected via environment variables (e.g., .env).
corpus_name = os.environ.get("RAG_CORPUS_NAME")
if not corpus_name:
    raise ValueError("RAG_CORPUS_NAME environment variable is not set.")

ask_vertex_retrieval = VertexAiRagRetrieval(
    name='retrieve_rag_documentation',
    description=(
        'Use this tool to retrieve legal contracts and documentation from the RAG corpus. '
        'You MUST use this tool to answer ANY question regarding the contracts, companies, or the knowledge base.'
    ),
    rag_resources=[
        rag.RagResource(
            rag_corpus=corpus_name
        )
    ],
    similarity_top_k=45,
    vector_distance_threshold=0.5,
)

root_agent = Agent(
    name='root_agent',
    model='gemini-2.5-pro',
    tools=[ask_vertex_retrieval],
    instruction='''You are a legal analyst using a RAG corpus. Synthesize the best possible answer using the provided context. If parts of the answer are missing from the context, explicitly state what is missing, but still provide the information you *do* have rather than refusing to answer entirely. Do NOT hallucinate.

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
- Delta LLC: The governing law is California. No amendments were found that shifted this jurisdiction.'''
)
