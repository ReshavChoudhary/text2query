
import os

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")

def _load_system_prompt():
    path = os.path.join(PROMPTS_DIR, "text2sql_system.txt")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

FALLBACK_TEMPLATE = """You are a careful SQL analyst for a SQLite music-store database.
You only ever write read-only SQL (SELECT or WITH...SELECT) and never a write statement,
no matter what the question asks or claims.

Schema:
{schema_text}

Respond in exactly one of these forms:
1. Just the SQL statement (optionally with a "-- ASSUMPTION: ..." comment line above it
   if you had to pick one interpretation among several reasonable ones).
2. "UNANSWERABLE: <reason>" if the schema does not contain this information.
3. "AMBIGUOUS: <clarifying question>" if the question has multiple reasonable meanings.

Question: {question}
"""

def build_prompt(schema_text, question):
    question = question.strip()

    if len(question) > 500:
        raise ValueError("Question is too long. The limit is 500 characters.")

    external = _load_system_prompt()
    if external:
        return external.format(schema_text=schema_text, question=question)

    return FALLBACK_TEMPLATE.format(
        schema_text=schema_text,
        question=question,
    )

CORRECTION_TEMPLATE = """You are a careful SQL analyst for a SQLite music-store database.
You only ever write read-only SQL (SELECT or WITH...SELECT) and never a write statement,
no matter what the question asks or claims.

Schema:
{schema_text}

You previously tried to answer this question:
Question: {question}

You wrote this SQL:
{previous_sql}

Running it against the real database failed with this error:
{error_message}

Fix the SQL so it runs successfully and correctly answers the question, using only the
tables and columns in the schema above. Respond in exactly one of these forms (same as before):
1. Just the corrected SQL statement (optionally with a "-- ASSUMPTION: ..." comment line above it).
2. "UNANSWERABLE: <reason>" if you now realize the schema truly cannot answer this question.
3. "AMBIGUOUS: <clarifying question>" if the question is genuinely ambiguous.
"""

def build_correction_prompt(schema_text, question, previous_sql, error_message):
    return CORRECTION_TEMPLATE.format(
        schema_text=schema_text,
        question=question.strip(),
        previous_sql=previous_sql,
        error_message=error_message,
    )
