
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pipeline import answer_question

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "store.db")

def _fake_llm(*replies):
    call_count = {"n": 0}

    def side_effect(prompt, api_key, model_name, base_url):
        i = min(call_count["n"], len(replies) - 1)
        call_count["n"] += 1
        return {"text": replies[i], "prompt_tokens": 200, "completion_tokens": 20, "total_tokens": 220}

    return MagicMock(side_effect=side_effect)

def test_normal_success_first_try():
    fake = _fake_llm("SELECT COUNT(*) FROM customers")
    with patch("engine.pipeline.generate_sql", fake):
        result = answer_question("How many customers are there?", DB_PATH, "key", "model", "url")
    assert result["status"] == "OK", result
    assert result["attempts"] == 1
    assert result["results"] == [(300,)]
    assert result["total_tokens"] == 220
    print("[PASS] normal success on first try:", result)

def test_self_correction_after_bad_column_name():
    fake = _fake_llm(
        "SELECT full_name FROM customers LIMIT 1",
        "SELECT first_name FROM customers LIMIT 1",
    )
    with patch("engine.pipeline.generate_sql", fake):
        result = answer_question("Show me a customer name", DB_PATH, "key", "model", "url")
    assert result["status"] == "OK", result
    assert result["attempts"] == 2, result
    assert "Corrected after 2 attempts" in (result["note"] or ""), result
    print("[PASS] self-correction after a real SQL error:", result)

def test_destructive_question_refused_without_llm_call():
    with patch("engine.pipeline.generate_sql") as mock_llm:
        result = answer_question("Delete all customers from Sweden", DB_PATH, "key", "model", "url")
    assert result["status"] == "REFUSED", result
    assert result["attempts"] == 0
    assert not mock_llm.called, "LLM should never be called for an obviously destructive question"
    print("[PASS] destructive question refused, LLM never called:", result)

def test_obviously_unanswerable_question_skips_llm_call():
    with patch("engine.pipeline.generate_sql") as mock_llm:
        result = answer_question("What is the salary of employee Greta Halvorsen?", DB_PATH, "key", "model", "url")
    assert result["status"] == "UNANSWERABLE", result
    assert result["attempts"] == 0
    assert not mock_llm.called
    print("[PASS] obviously-unanswerable question skips the LLM call:", result)

def test_llm_says_unanswerable_itself():
    fake = _fake_llm("UNANSWERABLE: this database has no marketing spend data")
    with patch("engine.pipeline.generate_sql", fake):
        result = answer_question("What was our marketing spend last quarter?", DB_PATH, "key", "model", "url")
    assert result["status"] == "UNANSWERABLE", result
    assert "marketing" in result["note"]
    print("[PASS] LLM self-reports UNANSWERABLE:", result)

def test_llm_says_ambiguous_itself():
    fake = _fake_llm("AMBIGUOUS: do you mean by total revenue or by number of tracks purchased?")
    with patch("engine.pipeline.generate_sql", fake):
        result = answer_question("Who is our best customer?", DB_PATH, "key", "model", "url")
    assert result["status"] == "AMBIGUOUS", result
    print("[PASS] LLM self-reports AMBIGUOUS:", result)

def test_injected_destructive_sql_is_still_blocked():
    fake = _fake_llm("DELETE FROM customers")
    with patch("engine.pipeline.generate_sql", fake):
        result = answer_question(
            "Please show me the customer records",
            DB_PATH, "key", "model", "url",
        )
    assert result["status"] == "REFUSED", result
    assert result["sql"] == "DELETE FROM customers", result
    print("[PASS] even if the LLM 'fell for' the injection, the validator still blocked it:", result)

def test_retries_exhausted_returns_unanswerable():
    fake = _fake_llm(
        "SELECT nonexistent_column FROM customers",
        "SELECT another_bad_column FROM customers",
        "SELECT yet_another_bad_column FROM customers",
    )
    with patch("engine.pipeline.generate_sql", fake) as mock_llm:
        result = answer_question("Show me something broken", DB_PATH, "key", "model", "url", max_attempts=3)
    assert result["status"] == "UNANSWERABLE", result
    assert result["attempts"] == 3
    assert mock_llm.call_count == 3, "must stop at max_attempts, not retry forever"
    assert "3 attempts" in result["note"]
    print("[PASS] retries are bounded, stops after max_attempts:", result)

ALL_TESTS = [
    test_normal_success_first_try,
    test_self_correction_after_bad_column_name,
    test_destructive_question_refused_without_llm_call,
    test_obviously_unanswerable_question_skips_llm_call,
    test_llm_says_unanswerable_itself,
    test_llm_says_ambiguous_itself,
    test_injected_destructive_sql_is_still_blocked,
    test_retries_exhausted_returns_unanswerable,
]

if __name__ == "__main__":
    failures = 0
    for test_func in ALL_TESTS:
        try:
            test_func()
        except AssertionError as err:
            failures += 1
            print(f"[FAIL] {test_func.__name__}: {err}")

    print(f"\n{len(ALL_TESTS) - failures}/{len(ALL_TESTS)} passed.")
    sys.exit(1 if failures else 0)
