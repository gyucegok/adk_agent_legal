"""RAG 2.0 Serverless Corpus Management Utility.

This script manages the lifecycle (setup, destroy, status) of a Vertex AI
RAG Engine 2.0 Serverless corpus backed by RagManagedVertexVectorSearch.

Note: Serverless mode backed by Vector Search 2.0 is supported exclusively
in the us-central1 region.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from dotenv import find_dotenv, load_dotenv
import vertexai
from vertexai.preview import rag


def load_configurations() -> dict[str, str]:
    """Loads and validates required environment variables.

    Returns:
        Dictionary containing project_id, location, corpus_display_name, and
        gcs_source_uri.

    Raises:
        ValueError: If PROJECT_ID is not provided in environment or .env.
    """
    load_dotenv(find_dotenv())

    project_id = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError(
            "PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set in .env or environment."
        )

    location = os.getenv("LOCATION", "us-central1")
    if location != "us-central1":
        print(
            f"WARNING: Serverless RAG 2.0 with RagManagedVertexVectorSearch is "
            f"supported only in 'us-central1'. Overriding location '{location}' to 'us-central1'."
        )
        location = "us-central1"

    corpus_name = os.getenv("LEGAL_CORPUS", "sec-legal-contracts-v2")
    gcs_uri = os.getenv("LEGAL_SOURCE_GCS_URI", "")
    if gcs_uri and not gcs_uri.startswith("gs://"):
        gcs_uri = f"gs://{gcs_uri}"

    return {
        "project_id": project_id,
        "location": location,
        "corpus_display_name": corpus_name,
        "gcs_source_uri": gcs_uri,
    }


def find_existing_corpus(
    display_name: str,
) -> Optional[rag.RagCorpus]:
    """Finds an existing RAG corpus by display name.

    Args:
        display_name: The human-readable display name of the RAG corpus.

    Returns:
        The matching RagCorpus object if found, otherwise None.
    """
    try:
        corpora = rag.list_corpora()
        for c in corpora:
            if c.display_name == display_name:
                return c
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Error checking existing corpora: {exc}")
    return None


def setup_corpus(
    project_id: str,
    location: str,
    corpus_display_name: str,
    gcs_source_uri: str,
) -> str:
    """Provisions a serverless RAG 2.0 corpus backed by Vector Search 2.0.

    Args:
        project_id: Google Cloud Project ID.
        location: Google Cloud region (must be us-central1).
        corpus_display_name: The display name for the corpus.
        gcs_source_uri: Cloud Storage URI containing legal documents.

    Returns:
        The full resource name of the created or existing RAG corpus.
    """
    print(f"Initializing Vertex AI in project={project_id}, location={location}...")
    vertexai.init(project=project_id, location=location)

    existing = find_existing_corpus(corpus_display_name)
    if existing:
        print(
            f"RAG corpus '{corpus_display_name}' already exists: {existing.name}"
        )
        return str(existing.name)

    print(
        f"Creating Serverless RAG 2.0 Corpus '{corpus_display_name}' "
        f"using RagManagedVertexVectorSearch..."
    )
    vector_db = rag.RagManagedVertexVectorSearch()
    rag_corpus = rag.create_corpus(
        display_name=corpus_display_name,
        backend_config=rag.RagVectorDbConfig(vector_db=vector_db),
    )
    print(f"Corpus successfully created: {rag_corpus.name}")

    if gcs_source_uri:
        print(f"Importing legal documents from {gcs_source_uri}...")
        transformation_config = rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(
                chunk_size=1024,
                chunk_overlap=200,
            )
        )
        rag.import_files(
            corpus_name=rag_corpus.name,
            paths=[gcs_source_uri],
            transformation_config=transformation_config,
            max_embedding_requests_per_min=1000,
        )
        print("Document ingestion completed successfully.")
    else:
        print(
            "LEGAL_SOURCE_GCS_URI is empty. Skipped document import. "
            "You can import documents later via the Vertex AI SDK."
        )

    print("\nNext step: Set RAG_CORPUS_NAME in your .env file:")
    print(f"RAG_CORPUS_NAME=\"{rag_corpus.name}\"")
    return str(rag_corpus.name)


def destroy_corpus(
    project_id: str,
    location: str,
    corpus_display_name: str,
) -> bool:
    """Destroys an existing RAG corpus and cleans up vector resources.

    Args:
        project_id: Google Cloud Project ID.
        location: Google Cloud region.
        corpus_display_name: The display name of the corpus to destroy.

    Returns:
        True if deleted, False if corpus was not found.
    """
    print(f"Initializing Vertex AI in project={project_id}, location={location}...")
    vertexai.init(project=project_id, location=location)

    existing = find_existing_corpus(corpus_display_name)
    if not existing:
        print(f"Corpus '{corpus_display_name}' not found. Nothing to delete.")
        return False

    print(f"Found corpus: {existing.name}. Deleting...")
    rag.delete_corpus(name=existing.name)
    print(f"Corpus '{corpus_display_name}' deleted successfully.")
    return True


def status_corpus(
    project_id: str,
    location: str,
    corpus_display_name: str,
) -> None:
    """Prints the status and details of the RAG corpus.

    Args:
        project_id: Google Cloud Project ID.
        location: Google Cloud region.
        corpus_display_name: The display name of the corpus.
    """
    vertexai.init(project=project_id, location=location)
    existing = find_existing_corpus(corpus_display_name)
    if existing:
        print(f"Status: ACTIVE")
        print(f"Corpus Display Name: {existing.display_name}")
        print(f"Resource Path: {existing.name}")
    else:
        print(f"Status: NOT_FOUND (Corpus '{corpus_display_name}' does not exist)")


def main() -> None:
    """CLI entry point for RAG 2.0 corpus management."""
    parser = argparse.ArgumentParser(
        description="Manage Vertex AI RAG 2.0 Serverless Corpora"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("setup", help="Create and populate RAG 2.0 corpus")
    subparsers.add_parser("destroy", help="Delete RAG 2.0 corpus")
    subparsers.add_parser("status", help="Check status of RAG 2.0 corpus")

    args = parser.parse_args()

    try:
        config = load_configurations()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.action == "setup":
        setup_corpus(
            project_id=config["project_id"],
            location=config["location"],
            corpus_display_name=config["corpus_display_name"],
            gcs_source_uri=config["gcs_source_uri"],
        )
    elif args.action == "destroy":
        destroy_corpus(
            project_id=config["project_id"],
            location=config["location"],
            corpus_display_name=config["corpus_display_name"],
        )
    elif args.action == "status":
        status_corpus(
            project_id=config["project_id"],
            location=config["location"],
            corpus_display_name=config["corpus_display_name"],
        )


if __name__ == "__main__":
    main()
