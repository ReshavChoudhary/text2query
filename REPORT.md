# Report — Text-to-SQL System for store.db

## 1. How the system works

The main idea of this project is simple. A user asks a question in normal English, the system converts it into SQL, runs the SQL on `store.db`, and returns the result as JSON.

I did not use any ready-made text-to-SQL library or agent framework for this. There is no LangChain, SQL Agent, or Vanna. I wrote the main logic using normal Python functions. The main flow is handled through `engine/pipeline.py`.

The flow is:

```
Question
   |
   v
[1] Quick checks
   |
   v
[2] Get schema
   |
   v
[3] Create prompt + call LLM
   |
   v
[4] Read LLM response
   |
   v
[5] Check SQL
   |
   v
[6] Run SQL
   |
   v
Answer as JSON
```

### Step 1 — Quick checks

This is handled by `guardrails/question_classifier.py`.

Before calling the LLM, the system checks the question. If the question looks destructive, such as asking to delete or update data, it returns `REFUSED`. If the question is clearly about data that is not available, it returns `UNANSWERABLE`. In both cases, the LLM is not called.

### Step 2 — Build the schema

This part uses `retriever/schema_retriever.py` and `retriever/table_selector.py`.

I tested two approaches here:

- **Approach A**: Send the complete schema of all 11 tables to the LLM.
- **Approach B**: Try to find the tables that are most relevant to the question and send only those tables.

### Step 3 — Create the prompt and call the LLM

The prompt is created in `chain/prompt_template.py`. The LLM call is handled by `chain/llm_client.py`. The model used in the evaluation was Groq's `openai/gpt-oss-120b`.

### Step 4 — Read the response

`chain/output_parser.py` reads the LLM response. The response can be:

- plain SQL
- `UNANSWERABLE: ...`
- `AMBIGUOUS: ...`

### Step 5 — Check the SQL

Every SQL query goes through `guardrails/sql_validator.py`. This check happens every time. There is no exception to this step.

### Step 6 — Run the query

`executor/query_executor.py` runs the SQL using a read-only SQLite connection. If SQLite returns an error, the system sends the error back to the LLM and tries to create a better query. There can be up to 3 attempts.

Finally, the system returns:

```json
{
  "sql": "...",
  "results": "...",
  "status": "...",
  "note": "..."
}
```

### Running the program

`ask.py` is the file I run from the command line. For example:

```
python ask.py --db store.db --question "Which customers are from Germany?"
```

The program is designed to return one JSON response even when something goes wrong. For example, if the database file or API key is missing, it should still return a clean response instead of showing a raw Python error.

### Why I added multiple safety checks

I did not want to depend only on the LLM following an instruction like "only generate SELECT queries." There are four checks in the system.

**1. Prompt instructions** — `prompts/text2sql_system.txt` tells the LLM to generate only `SELECT` or `WITH...SELECT` queries. It also tells the model to treat the user's question as data and not as a new instruction. This is useful, but I don't consider the prompt itself enough for security.

**2. SQL validator** — `guardrails/sql_validator.py` uses an allowlist. The query must start with `SELECT` or `WITH`. It also rejects multiple statements joined with `;`. Another check is needed for cases where a `WITH` query tries to hide a `DELETE`, `UPDATE`, `INSERT`, or `REPLACE` statement at the end. I tested this using 34 handwritten attack cases in `tests/test_sql_validator_attacks.py`. All 34 were handled correctly.

**3. Read-only database connection** — `executor/query_executor.py` opens SQLite using `file:{db_path}?mode=ro`, so the original database is opened in read-only mode. This gives another layer of protection even if something gets past the SQL validator.

**4. Execute only the checked SQL** — after SQL is checked, the same SQL is executed. There is no second code path that creates a new SQL query after validation.

### About the question classifier

`guardrails/question_classifier.py` is mainly a quick check. It is useful because obvious destructive or unanswerable questions can be stopped early. But it is not the main security layer. Even if I remove this file, the SQL validator and read-only database connection would still block the destructive and injection cases from my test set.

### Two ways of sending the schema

**Approach A — Full schema.** For every question, the LLM gets the schema of all 11 tables. I also added notes about two tables that need special care. These are explained later in the limitations section.

**Approach B — Selected tables.** `retriever/table_selector.py` tries to select only the tables related to the question. It gives a score to each table based on:

- table name appearing in the question
- column name appearing in the question
- words from a small synonym list

For example, words such as "spent" or "revenue" can point to the `invoices` table. The selector also adds tables connected through foreign keys. This is important because a query may need a join. The idea behind Approach B was to send less schema information to the LLM.

## 2. Results

I ran both approaches on all 55 questions from `eval_set.json` using Groq with `openai/gpt-oss-120b`.

For grading, I compared the actual result rows with a hand-checked correct answer. I did not simply compare the generated SQL text. The comparison is done using `results_match()` in `evaluate.py`.

| Approach | Accuracy | Avg tokens/question | Avg latency/question | Avg attempts | Total wall time |
|---|---|---|---|---|---|
| A — full schema | 89.1% (49/55) | 1544.1 | 4.59s | 0.73 | 252.5s |
| B — selected tables | 87.3% (48/55) | 1116.7 | 5.32s | 0.73 | 292.7s |

The average number of attempts is below 1 because 15 of the 55 questions were caught by the quick checks before reaching the LLM. These questions therefore count as 0 attempts.

### Accuracy by category

| Category | A | B |
|---|---|---|
| lookup | 5/5 (100%) | 5/5 (100%) |
| filter | 4/5 (80%) | 4/5 (80%) |
| sort_topn | 3/5 (60%) | 3/5 (60%) |
| aggregation | 4/5 (80%) | 4/5 (80%) |
| join | 5/6 (83.3%) | 5/6 (83.3%) |
| date_filter | 5/5 (100%) | 5/5 (100%) |
| business | 3/4 (75%) | 3/4 (75%) |
| unanswerable | 5/5 (100%) | 5/5 (100%) |
| ambiguous | 5/5 (100%) | 4/5 (80%) |
| destructive | 5/5 (100%) | 5/5 (100%) |
| injection | 5/5 (100%) | 5/5 (100%) |

### What I noticed from the results

Both approaches blocked every destructive and injection question in the test set. There were 10 such questions in total, and all 10 were blocked.

Approach A had slightly better accuracy: 89.1% compared with 87.3% for Approach B.

However, Approach B used fewer tokens — about 28% fewer tokens per question than Approach A (the same gap can also be stated the other way round: Approach A used about 38% more tokens per question than Approach B).

The two approaches mainly differed in the ambiguous category. In one case, the full schema gave Approach A enough information to understand that the question could be answered but was not specific enough. Approach B had less schema information, so it decided that the required data was not available.

Approach B also did not turn out to be faster in this run. Since only 55 questions were tested and Groq's rate limit affected the run, I would not use this small latency difference to make a strong conclusion. Token usage is a better comparison here.

### Self-correction

The retry mechanism was not needed during this actual 55-question run. All 40 questions that reached the LLM produced a working query on the first try.

The retry code still exists: `MAX_ATTEMPTS = 3` in `engine/pipeline.py`. I tested the retry logic separately in `tests/test_pipeline_mock.py` using a fake LLM that keeps failing. The test also checks that the system stops after 3 attempts if it cannot recover.

## 3. Failures I found

The assignment asks for 10 worst failures. In my actual run, I found only 7 failures. I am listing those 7 instead of creating three extra examples just to reach 10. I checked these cases against the actual database.

**1. id=10 — "Which invoices were billed to Germany?"** (both approaches)

The system generated `SELECT inv_id FROM invoices WHERE ctry_cd = 'Germany'`. This returns the correct 94 invoice IDs. The expected answer also contained `inv_date` and `inv_amt_net`. The grading script compares complete rows, so the answer with only `inv_id` did not match the expected rows. So in this case, the SQL itself is correct — the problem is with the strict grading method.

**2. id=13 — "Which 3 albums have the most tracks?"** (both approaches)

There are multiple albums tied at 12 tracks. Because the query uses `ORDER BY ... LIMIT 3` without a second column to break the tie, different albums can be returned. So this is mainly a tie in the data rather than a bug in the system.

**3. id=15 — "What are the top 5 genres by number of tracks?"**

This is similar to the previous case. There is a tie around the 5th position between Electronic and Metal/Blues. Without a tiebreaker, different results can be valid.

**4. id=19 — "What is the average satisfaction score for resolved support tickets?"**

The `support_tickets.status` column has four values: `Open`, `Escalated`, `Resolved`, `Closed`. My system used `resolved_dt IS NOT NULL`, which includes both `Resolved` and `Closed` — 295 rows, average 3.61. The hand-written expected answer used `status = 'Resolved'`, giving 217 rows, average 3.57. Both interpretations make sense because the schema does not clearly say whether `Closed` should also be treated as resolved.

**5. id=24 — "Who is the support representative for customer Freya Fernandes?"** (both approaches)

My system returned one combined column: `SELECT first_name || ' ' || last_name AS support_rep ...`, giving `"Lukas Brenner"`. The expected answer used two columns, `SELECT first_name, last_name`, giving `Lukas | Brenner`. The person is the same — the difference is only in how the result is formatted. Again, this is a limitation of the grading script.

**6. id=33 — "What percentage of support tickets are still open?"**

This has a similar problem to failure #4. My system used `resolved_dt IS NULL`, which includes both `Open` and `Escalated`, giving 29.76%. The expected answer used `status = 'Open'`, giving 16.19%. The schema does not clearly define whether an `Escalated` ticket should be counted as still open.

**7. id=43 — "Which employee performs the best?"** (Approach B only)

Approach A had the full schema and understood that the question was too vague. It asked which metric should be used, such as sales, resolved tickets, or satisfaction score — this was graded as correct. Approach B did not select enough relevant tables for the word "performance." Because of the smaller schema, the model decided that there was no performance data and returned `UNANSWERABLE`. This is a real weakness of the table-selection approach.

### Summary of the 7 failures

The failures had different reasons: #1 and #5 were mainly grading-format problems; #2 and #3 were caused by ties in the data; #4 and #6 came from unclear meanings of "resolved" and "open"; #7 was a real accuracy problem caused by the smaller schema in Approach B. None of these were safety failures.

## 4. How my system could be made to run a destructive query

I tested the system with 34 handwritten SQL attack cases and 10 destructive/injection questions. All of them were blocked. However, I found two areas where the current design could be improved.

**1. ATTACH DATABASE**

SQLite's `mode=ro` protects the original database file, but it does not automatically make another attached database read-only. I tested this by opening `file:store.db?mode=ro` and then using `ATTACH DATABASE 'evil.db' AS x`. SQLite can still create tables and insert data into the attached file, because the read-only setting applies only to the original database file.

This attack does not currently work through my system because `guardrails/sql_validator.py` rejects `ATTACH` before it reaches SQLite. So the current protection for this case depends on the SQL allowlist. If that check were bypassed in the future — for example because of a parsing problem, or because some new code calls `run_query()` directly without using `check_safety()` — this could become a problem.

**2. SQLite functions that can access files**

Some SQLite functions can interact with the filesystem. For example, `SELECT writefile(...)` could be a concern if the function were available. I tested this in the current environment: `writefile()` is not available in the standard Python `sqlite3` setup being used, so it currently gives a "no such function" error.

The issue is that the SQL validator mainly checks the statement type. A query starting with `SELECT` is allowed, even if it contains a function that could potentially have side effects in another SQLite environment. A better design would allow only a known list of safe SQL functions.

### Why I am mentioning these issues

The system passed all the attack cases I tested, but that does not mean it is guaranteed to stop every possible attack. These two cases show the limits of the current design, especially around SQLite features that can affect files outside the original database.

## 5. Limitations

1. **Approach B depends on a hand-written synonym list.** Approach B uses keywords and synonyms written by me in `retriever/table_selector.py`. If a user uses a word that is not in the `SYNONYMS` list, the selector may not find the right table. Failure #7 is an example of this.
2. **Two tables need special care.** `customer_archive` contains former customers and is separate from `customers`. `sales_summary` is an old cache table and should not be used for totals. I added warnings for both tables in `TABLE_NOTES` inside `retriever/schema_retriever.py`. However, the model could still select the wrong table if the question is worded in a way that does not make the difference clear.
3. **Dates use different formats.** There are two date formats in the database: `invoices.inv_date` and `customers.signup_dt` use `YYYY-MM-DD`, while `support_tickets.opened_dt` and `resolved_dt` use `DD-MM-YYYY`. Currently, this difference is mentioned to the model through `COLUMN_NOTES`, but the data itself is not normalized.
4. **The grading script is strict.** `evaluate.py` compares result values quite strictly. It handles things like extra columns, different column order, and small rounding differences. But it does not understand some cases where two answers mean the same thing — for example, combining `first_name` and `last_name` into one column can be semantically the same as returning them as two columns. It also does not understand that a shorter answer can still contain the correct information. A better grader would compare the meaning of the answer rather than only exact values.
5. **Top-N questions can have ties.** Questions such as "top 3" or "top 5" can have multiple valid answers when two rows have the same value at the cutoff. A fixed tiebreaker would make these results consistent.
6. **"Resolved" and "open" can be unclear.** The support ticket table has four possible statuses. Because of this, words like "resolved" and "open" can sometimes have more than one reasonable meaning. The system may need to ask the user for clarification in such cases.
7. **ATTACH and filesystem functions.** The `ATTACH` and filesystem-function issues explained in Section 4 are real limitations of the current SQL validation approach.
8. **Groq rate limit.** Groq's free tier has a rate limit of 8000 tokens/minute for `openai/gpt-oss-120b`. This slowed down the 55-question evaluation — the complete run took about 9 minutes because `chain/llm_client.py` waits and retries when the limit is reached. This is a service limitation, not a bug in my code.
9. **Self-correction was not needed in the real evaluation.** The retry mechanism was not used during the actual 55-question run because all 40 questions that reached the LLM worked on the first attempt. The retry logic was still tested separately using the fake LLM in `tests/test_pipeline_mock.py`.

## 6. What I would improve with another week

If I had another week, I would work on these areas:

- Replace the keyword-based table selector with a lightweight embedding-based retriever. I would still build the logic myself instead of using a framework.
- Improve `guardrails/sql_validator.py` so it also checks which SQL functions are allowed.
- Normalize the different date formats when reading the data.
- Add a fixed tiebreaker such as `id ASC` for Top-N queries.
- Improve `evaluate.py` so it can recognize answers that are different in format but have the same meaning.
- Add a small cache in `evaluate.py` so an interrupted evaluation does not have to start all 55 questions again.

Overall, the system is working well for the tested dataset. Approach A gave slightly better accuracy, while Approach B reduced token usage. The main areas I would focus on next are better table selection, stronger SQL validation, and a more flexible evaluation method.
