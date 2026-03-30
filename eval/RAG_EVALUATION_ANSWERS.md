# RAG Engine Evaluation Answers (Grading Rubric)

This document contains the evaluation rubrics and expected answers for the 5 questions outlined in `RAG_EVALUATION_QUESTIONS.md`.

### 1. Clause Override Detection - Lockheed Martin
* **Expected Document Sources:** `lmt_family_3` documents.
* **Rubric:**
    * **Full Points:** Accurately locates the "Termination" clause. Identifies the exact Amendment number or document name that overrides these clauses. Clearly states the *delta* (e.g., "The termination date changed from X to Y"). Explicitly notes if the original date is missing from the retrieved context.
    * **Partial Points:** Identifies that a change occurred but vaguely describes the delta, or finds the final clause without acknowledging the original baseline.

### 2. Synthesizing Net-New Obligations - The Walt Disney Company
* **Expected Document Sources:** `dis_family_14` documents.
* **Rubric:**
    * **Full Points:** Performs a semantic "diff" comparing the master agreement's compliance/reporting covenants with those in the amendments. Must explicitly name the *newly added* requirements (e.g., new ESG reporting, new data delivery schedules) that were strictly absent from the master document.
    * **Partial Points:** Lists obligations found in the amended document but fails to distinguish which ones were pre-existing vs. net-new.

### 3. Entity Addition/Removal - UnitedHealth Group
* **Expected Document Sources:** `unh_family_2` exhibits.
* **Rubric:**
    * **Full Points:** Explicitly lists the specific domestic corporate subsidiaries found in the documents that were added as guarantors/parties in an amendment (e.g. Optum Select Management, Inc., United HealthCare Services, Inc., Health Plan of Nevada, Inc.).
    * **Partial Points:** Identifies only "Optum" or "UHC" generally without the specific legal entity names.
    * **Failure:** Fails to list entities that were added.

### 4. Tracing Definitions - Comcast
* **Expected Document Sources:** `cmcsa_family_1`.
* **Rubric:**
    * **Full Points:** Locates the "Definitions" section of the Master Agreement or Amendment. Quotes the original definition for 'Marketable Securities'. Locates the exact amendment where the definition was replaced or expanded and quotes the final definition. Explicitly notes if the original or amended definition is missing from context.
    * **Failure:** Retrieves only the old definition or blends the two definitions into an incoherent hallucination without explicitly stating what is missing.

### 5. Cross-Family Comparison (Meta-Analysis) - BoA vs GS
* **Expected Document Sources:** `bac_family_7`, `gs_family_0`.
* **Rubric:**
    * **Full Points:** The agent successfully executes a multi-hop query across different directories. It correctly states the Governing Law for Bank of America, compares it to Goldman Sachs, and identifies if any amendment shifted the jurisdiction or arbitration rules.
    * **Partial Points:** Identifies the governing law for one institution but fails to retrieve the context for the others, failing the comparative analysis.