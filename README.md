# Text-to-SQL for store.db

Turns a plain-English question into a safe, read-only SQL query, runs it against `store.db`, and prints one JSON answer. No LangChain, no text-to-SQL library, no agent framework -- every step (schema retrieval, prompting, SQL safety checks, execution, bounded self-correction) is plain Python you can read end to end in `engine/pipeline.py`.

See `REPORT.md` for the architecture write-up, the real accuracy/token/latency numbers for both approaches, all failures found during evaluation, and the security analysis.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and add your own key:
   ```
   cp .env.example .env
   ```
   Get a free API key from https://console.groq.com 

## Usage

Ask a question (Approach A, full schema -- the default):
```
python ask.py --db store.db --question "Which 5 customers spent the most in 2024?"
```

Use Approach B (only relevant tables selected) instead:
```
python ask.py --db store.db --question "Which 5 customers spent the most in 2024?" --approach selected
```

Every run prints exactly one JSON object:
```json
{"sql": "...", "results": [...], "status": "OK", "note": null}
```
`status` is one of `OK`, `AMBIGUOUS`, `UNANSWERABLE`, `REFUSED`. A destructive question (e.g. "delete all customers") always comes back `REFUSED` -- it is never sent to a write-capable connection; see `REPORT.md` section 1 for why.

## Evaluation

Run all 55 hand-written evaluation questions (`eval_set.json`) through both approaches and print/store accuracy, token usage, and latency:
```
python evaluate.py --db store.db
```
This makes real LLM calls, so it uses some of your Groq quota and takes a few minutes (Groq's free tier has a strict tokens-per-minute limit; `chain/llm_client.py` automatically waits and retries when it hits that limit). Detailed per-question results are saved to `eval_results.json`.

## Tests

Every test below runs against mocked LLM responses or the real `store.db` file directly -- none of them call the real Groq API, so they run instantly and don't use any quota:
```
python tests/test_sql_validator_attacks.py    # 34 adversarial SQL-injection / destructive-SQL cases
python tests/test_question_classifier.py      # fast pre-check logic
python tests/test_table_selector.py           # Approach B's table-selection heuristic
python tests/test_output_parser.py            # parsing the LLM's SQL / UNANSWERABLE / AMBIGUOUS reply
python tests/test_pipeline_mock.py            # the full pipeline, with a mocked LLM
python tests/test_llm_client_mock.py          # LLM client, including rate-limit retry
python tests/test_evaluate_logic.py           # evaluate.py's grading logic
python tests/test_eval_set_sql.py             # every gold SQL answer in eval_set.json actually runs
```

## Project structure

```
ask.py                      CLI entry point
evaluate.py                 Runs eval_set.json through both approaches, grades results
eval_set.json                55 hand-written evaluation questions
REPORT.md                   Architecture, results, failures, security analysis, limitations
requirements.txt            Exact-pinned dependencies

config/settings.py          Loads GROQ_API_KEY / model / base URL from .env
retriever/schema_retriever.py   Reads schema from SQLite (Approach A)
retriever/table_selector.py     Picks relevant tables by keyword/synonym match (Approach B)
chain/prompt_template.py    Builds the prompt sent to the LLM (+ the self-correction prompt)
chain/llm_client.py         Calls Groq's Chat Completions API directly (no framework)
chain/output_parser.py      Parses the LLM's reply into SQL / UNANSWERABLE / AMBIGUOUS
guardrails/question_classifier.py   Fast pre-checks (NOT the security boundary -- see REPORT.md)
guardrails/sql_validator.py Allowlist-based SQL safety check (the real security boundary)
executor/query_executor.py  Executes SQL on a genuinely read-only SQLite connection
engine/pipeline.py           Wires all of the above together end to end
tests/                       All unit/regression tests (no real API calls)
scripts/build_eval_set.py    Script used to generate eval_set.json
```

## Security note

Read `REPORT.md` section 4, "How my system could be made to run a destructive query," for an honest account of the one real remaining gap (SQL functions like `writefile()` that are not currently blocked by name, only inactive because this environment's SQLite build doesn't compile them in) -- found by trying to attack the system myself, not left undiscovered.
