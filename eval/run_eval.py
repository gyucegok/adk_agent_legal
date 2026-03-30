import os
import re
import json
import sys
import asyncio
from dotenv import load_dotenv, find_dotenv

# Load env vars
load_dotenv(find_dotenv())

# Ensure we can import the agent from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from agent_with_rag.agent import corpus_name
except ImportError as e:
    print(f"Error importing agent properties: {e}")
    sys.exit(1)

import vertexai
from vertexai.preview.generative_models import GenerativeModel, Tool
import vertexai.preview.rag as rag
from google import genai

# Initialize vertex ai
vertexai.init(project=os.environ.get("PROJECT_ID"), location=os.environ.get("LOCATION"))

# Recreate the tool and model natively to bypass ADK execution bug
rag_retrieval_tool = Tool.from_retrieval(
    retrieval=rag.Retrieval(
        source=rag.VertexRagStore(
            rag_resources=[rag.RagResource(rag_corpus=corpus_name)],
            similarity_top_k=45,
            vector_distance_threshold=0.5,
        ),
    )
)

agent_model = GenerativeModel(
    "gemini-2.5-pro",
    tools=[rag_retrieval_tool],
    system_instruction='''You are a legal analyst using a RAG corpus. Synthesize the best possible answer using the provided context. If parts of the answer are missing from the context, explicitly state what is missing, but still provide the information you *do* have rather than refusing to answer entirely. Do NOT hallucinate.

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

eval_client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location=os.environ.get("LOCATION"))

def extract_sections(filepath, pattern, extract_group=True):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return []
    with open(filepath, 'r') as f:
        content = f.read()
    
    sections = content.split('### ')[1:]
    extracted = []
    for sec in sections:
        if extract_group:
            match = re.search(pattern, sec, re.DOTALL)
            if match:
                extracted.append(match.group(1).strip())
            else:
                extracted.append(sec.strip())
        else:
            extracted.append(sec.strip())
    return extracted

def load_data():
    questions_file = os.path.join(os.path.dirname(__file__), 'RAG_EVALUATION_QUESTIONS.md')
    answers_file = os.path.join(os.path.dirname(__file__), 'RAG_EVALUATION_ANSWERS.md')
    
    q_pattern = r'\*\*Question:\*\*\s*"(.*?)"'
    questions = extract_sections(questions_file, q_pattern, extract_group=True)
    rubrics = extract_sections(answers_file, r'', extract_group=False)
    
    return questions, rubrics

def evaluate_answer(question, answer, rubric):
    prompt = f"""
You are an expert evaluator grading a RAG-based legal AI agent.
Please evaluate the agent's answer to the following question based on the provided grading rubric.

Question: {question}

Agent's Answer:
{answer}

Grading Rubric:
{rubric}

Provide your evaluation in the following format:
SCORE: [Full Points / Partial Points / Failure]
REASONING: [Brief explanation of why this score was given based on the rubric]
"""
    response = eval_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

async def main():
    print("Loading evaluation data...")
    questions, rubrics = load_data()
    
    if not questions or not rubrics:
        print("Failed to load questions or rubrics. Check file paths.")
        return
        
    print(f"Loaded {len(questions)} questions and {len(rubrics)} rubrics.")
    
    if len(questions) != len(rubrics):
        print("Warning: Number of questions does not match number of rubrics!")
        
    results = []
    
    for i, (q, r) in enumerate(zip(questions, rubrics)):
        print(f"\n{'='*50}")
        print(f"Evaluating Question {i+1}/{len(questions)}")
        print(f"Q: {q}")
        print(f"{'='*50}")
        
        print("\nQuerying agent (this may take a moment)...")
        answer_text = ""
        try:
            # Use native GenerativeModel generate_content to invoke RAG
            response = agent_model.generate_content(q)
            answer_text = response.text
        except Exception as e:
            answer_text = f"Error querying agent: {e}"
            
        print(f"\nAgent Answer:\n{answer_text}\n")
        
        print("Grading answer with LLM judge...")
        try:
            evaluation = evaluate_answer(q, answer_text, r)
        except Exception as e:
            evaluation = f"Error grading answer: {e}"
            
        print(f"\nEvaluation Result:\n{evaluation}\n")
        
        results.append({
            "question_number": i + 1,
            "question": q,
            "agent_answer": answer_text,
            "rubric": r,
            "evaluation": evaluation
        })
        
    output_file = os.path.join(os.path.dirname(__file__), 'evaluation_results.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nEvaluation complete. Detailed results saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())