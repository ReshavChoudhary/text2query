
import time

from guardrails.question_classifier import check_destructive_intent, check_obviously_unanswerable
from guardrails.sql_validator import check_safety
from retriever.schema_retriever import read_schema
from retriever.table_selector import build_schema_for_question
from chain.prompt_template import build_prompt, build_correction_prompt
from chain.llm_client import generate_sql
from chain.output_parser import parse_llm_reply
from executor.query_executor import run_query

MAX_ATTEMPTS = 3

def answer_question(question, db_path, api_key, model_name, base_url,
                     approach="full", max_attempts=MAX_ATTEMPTS):
    start_time = time.time()

    if check_destructive_intent(question):
        return _result(None, [], "REFUSED",
                        "This question asks to change data. Only read-only questions are supported.",
                        0, 0, start_time)

    is_unanswerable, reason = check_obviously_unanswerable(question)
    if is_unanswerable:
        return _result(None, [], "UNANSWERABLE", reason, 0, 0, start_time)

    try:
        if approach == "selected":
            schema_text = build_schema_for_question(question, db_path)
        else:
            schema_text = read_schema(db_path)
        prompt = build_prompt(schema_text, question)
    except ValueError as err:
        return _result(None, [], "UNANSWERABLE", str(err), 0, 0, start_time)
    except (ConnectionError, OSError) as err:
        return _result(None, [], "UNANSWERABLE", f"Could not read the database schema: {err}", 0, 0, start_time)

    sql = None
    last_error = None
    total_tokens = 0

    for attempt_number in range(1, max_attempts + 1):
        try:
            llm_result = generate_sql(prompt, api_key, model_name, base_url)
        except (ValueError, TimeoutError, RuntimeError) as err:
            return _result(sql, [], "UNANSWERABLE", f"The LLM call failed: {err}",
                            attempt_number, total_tokens, start_time)

        if llm_result.get("total_tokens"):
            total_tokens += llm_result["total_tokens"]

        parsed = parse_llm_reply(llm_result["text"])

        if parsed["kind"] == "unanswerable":
            return _result(None, [], "UNANSWERABLE", parsed["reason"], attempt_number, total_tokens, start_time)

        if parsed["kind"] == "ambiguous":
            return _result(None, [], "AMBIGUOUS", parsed["clarification"], attempt_number, total_tokens, start_time)

        sql = parsed["sql"]
        assumption = parsed["assumption"]

        if not sql:
            last_error = "The model did not return a usable SQL statement."
            prompt = build_correction_prompt(schema_text, question, "(no SQL returned)", last_error)
            continue

        allowed, block_reason = check_safety(sql)
        if not allowed:
            return _result(sql, [], "REFUSED", f"Blocked before execution: {block_reason}",
                            attempt_number, total_tokens, start_time)

        try:
            query_result = run_query(sql, db_path)
        except Exception as err:
            last_error = str(err)
            prompt = build_correction_prompt(schema_text, question, sql, last_error)
            continue

        note = f"Assumption: {assumption}" if assumption else None
        if attempt_number > 1:
            retry_note = f"Corrected after {attempt_number} attempts."
            note = f"{note} {retry_note}" if note else retry_note
        return _result(sql, query_result["rows"], "OK", note, attempt_number, total_tokens, start_time)

    return _result(sql, [], "UNANSWERABLE",
                    f"Could not produce a working query after {max_attempts} attempts. Last error: {last_error}",
                    max_attempts, total_tokens, start_time)

def _result(sql, results, status, note, attempts, total_tokens, start_time):
    return {
        "sql": sql,
        "results": results,
        "status": status,
        "note": note,
        "attempts": attempts,
        "total_tokens": total_tokens if total_tokens else None,
        "latency_seconds": round(time.time() - start_time, 3),
    }
