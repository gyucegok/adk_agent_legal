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

PYTHON_EXEC=".venv/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Error: Python virtual environment not found at .venv"
    exit 1
fi

LEGAL_CORPUS="sec-legal-contracts"

echo "Attempting to destroy RAG corpus '${LEGAL_CORPUS}'..."

# Use Python to find and delete the corpus
$PYTHON_EXEC -c "
import vertexai
from vertexai import rag
import os

try:
    vertexai.init(project='$PROJECT_ID', location='$LOCATION')
    corpora = rag.list_corpora()
    target_corpus = next((c for c in corpora if c.display_name == '$LEGAL_CORPUS'), None)
    
    if target_corpus:
        print(f'Found corpus: {target_corpus.name}. Deleting...')
        rag.delete_corpus(name=target_corpus.name)
        print('Corpus deleted successfully.')
    else:
        print(f'Corpus \'{LEGAL_CORPUS}\' not found.')

except Exception as e:
    print(f'Error: {e}')
    exit(1)
"
