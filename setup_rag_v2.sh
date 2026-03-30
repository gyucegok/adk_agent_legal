#!/bin/bash
set -e

# Source environment variables
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    # Load env vars, handling spaces around =
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ $key =~ ^#.*$ ]] || [[ -z $key ]] && continue
        # Remove whitespace from key
        key=$(echo "$key" | xargs)
        # Remove whitespace and quotes from value
        value=$(echo "$value" | xargs | sed -e 's/^"//' -e 's/"$//')
        export "$key=$value"
    done < "$ENV_FILE"
else
    echo "Error: $ENV_FILE not found."
    exit 1
fi

# Path to python
PYTHON_EXEC=".venv/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Error: Python virtual environment not found at .venv"
    exit 1
fi

LEGAL_CORPUS="sec-legal-contracts"
LEGAL_SOURCE_GCS_URI="legal-agent-contracts-gyucegok-alto"

echo "Checking if RAG corpus '${LEGAL_CORPUS}' exists..."

# Check if corpus exists using a python one-liner
EXISTS=$($PYTHON_EXEC -c "
import vertexai
from vertexai import rag
import os

try:
    vertexai.init(project='$PROJECT_ID', location='$LOCATION')
    corpora = rag.list_corpora()
    found = any(c.display_name == '$LEGAL_CORPUS' for c in corpora)
    print('true' if found else 'false')
except Exception as e:
    print(f'Error: {e}')
    exit(1)
")

if [ "$EXISTS" == "true" ]; then
    echo "RAG corpus '${LEGAL_CORPUS}' already exists. Skipping setup."
else
    echo "RAG corpus not found. Running setup..."
    
    # Embedded python script for RAG setup
    $PYTHON_EXEC - <<EOF
from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
import vertexai
import os

# Environment variables are already exported by the bash wrapper
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
LEGAL_CORPUS = "$LEGAL_CORPUS"
LEGAL_SOURCE_GCS_URI = "gs://$LEGAL_SOURCE_GCS_URI"

print(f"Initializing Vertex AI for project {PROJECT_ID} in {LOCATION}...")
vertexai.init(project=PROJECT_ID, location=LOCATION)

paths = [LEGAL_SOURCE_GCS_URI]

print(f"Creating RAG Corpus: {LEGAL_CORPUS}")
# Configure embedding model
embedding_model_config = rag.RagEmbeddingModelConfig(
    vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
        publisher_model="publishers/google/models/text-embedding-005"
    )
)

rag_corpus = rag.create_corpus(
    display_name=LEGAL_CORPUS,
    backend_config=rag.RagVectorDbConfig(
        rag_embedding_model_config=embedding_model_config
    ),
)

print(f"Importing files from {paths}...")
rag.import_files(
    rag_corpus.name,
    paths,
    transformation_config=rag.TransformationConfig(
        chunking_config=rag.ChunkingConfig(
            chunk_size=1024,
            chunk_overlap=200,
        ),
    ),
    max_embedding_requests_per_min=1000,
)
print("Setup complete.")
EOF

fi
