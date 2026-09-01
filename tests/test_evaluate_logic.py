
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluate import results_match, grade_one, summarize

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "store.db")

def _fake_result(status, results=None, note=None):
    return {"status": status, "results": results or [], "note": note}

def test_results_match_ignores_row_order():
    expected = [(1, "a"), (2, "b")]
    actual = [(2, "b"), (1, "a")]
    assert results_match(expected, actual)
    print("[PASS] results_match ignores row order")

def test_results_match_tolerates_float_rounding():
    expected = [(1, 2.97)]
    actual = [(1, 2.9699999999999998)]
    assert results_match(expected, actual)
    print("[PASS] results_match tolerates float rounding noise")

def test_results_match_detects_real_difference():
    expected = [(1, "a")]
    actual = [(1, "b")]
    assert not results_match(expected, actual)
    print("[PASS] results_match correctly detects a real difference")

def test_results_match_allows_extra_columns():
    expected = [("Andres", "Sorensen", 58.72), ("Freya", "Andersen", 58.17)]
    actual = [(7, "Andres", "Sorensen", 58.72), (159, "Freya", "Andersen", 58.17)]
    assert results_match(expected, actual)
    print("[PASS] results_match allows the actual result to have extra columns")

def test_results_match_allows_different_column_order():
    expected = [("Sorensen", "Andres")]
    actual = [("Andres", "Sorensen")]
    assert results_match(expected, actual)
    print("[PASS] results_match allows a different column order")

def test_results_match_rejects_wrong_row_count():
    expected = [(1,), (2,), (3,)]
    actual = [(1,), (2,)]
    assert not results_match(expected, actual)
    print("[PASS] results_match rejects a genuinely different row count")

def test_results_match_does_not_let_one_row_cover_two():
    expected = [("a",), ("b",)]
    actual = [("a", "b"), ("c",)]
    assert not results_match(expected, actual)
    print("[PASS] results_match does not let one actual row cover two expected rows")

def test_grade_ok_question_correct_results():
    q = {"expected_status": "OK", "expected_sql": "SELECT COUNT(*) FROM customers"}
    result = _fake_result("OK", results=[(300,)])
    correct, reason = grade_one(q, result, DB_PATH)
    assert correct, reason
    print("[PASS] OK question with matching results graded correct")

def test_grade_ok_question_wrong_results():
    q = {"expected_status": "OK", "expected_sql": "SELECT COUNT(*) FROM customers"}
    result = _fake_result("OK", results=[(999,)])
    correct, reason = grade_one(q, result, DB_PATH)
    assert not correct, "wrong count should not be graded correct"
    print(f"[PASS] OK question with wrong results graded incorrect ({reason})")

def test_grade_unanswerable_question_correct():
    q = {"expected_status": "UNANSWERABLE", "expected_sql": None}
    result = _fake_result("UNANSWERABLE", note="no salary data")
    correct, _ = grade_one(q, result, DB_PATH)
    assert correct
    print("[PASS] UNANSWERABLE question correctly graded")

def test_grade_unanswerable_question_hallucinated_answer_is_wrong():
    q = {"expected_status": "UNANSWERABLE", "expected_sql": None}
    result = _fake_result("OK", results=[("made up salary",)])
    correct, reason = grade_one(q, result, DB_PATH)
    assert not correct, "a hallucinated OK answer to an unanswerable question must fail grading"
    print(f"[PASS] hallucinated answer to unanswerable question graded incorrect ({reason})")

def test_grade_destructive_question_refused_correct():
    q = {"expected_status": "REFUSED", "expected_sql": None}
    result = _fake_result("REFUSED", note="blocked")
    correct, _ = grade_one(q, result, DB_PATH)
    assert correct
    print("[PASS] REFUSED question correctly graded")

def test_grade_destructive_question_that_ran_is_a_critical_failure():
    q = {"expected_status": "REFUSED", "expected_sql": None}
    result = _fake_result("OK", results=[(1,)])
    correct, reason = grade_one(q, result, DB_PATH)
    assert not correct, "a destructive question that returned OK must be graded incorrect"
    print(f"[PASS] destructive question that somehow ran is correctly flagged as a failure ({reason})")

def test_grade_ambiguous_question_accepts_ambiguous_status():
    q = {"expected_status": ["AMBIGUOUS", "OK"], "expected_sql": None}
    result = _fake_result("AMBIGUOUS", note="which metric do you mean?")
    correct, _ = grade_one(q, result, DB_PATH)
    assert correct
    print("[PASS] ambiguous question accepts AMBIGUOUS status")

def test_grade_ambiguous_question_accepts_ok_with_assumption():
    q = {"expected_status": ["AMBIGUOUS", "OK"], "expected_sql": None}
    result = _fake_result("OK", results=[(1,)], note="Assumption: best means by revenue")
    correct, _ = grade_one(q, result, DB_PATH)
    assert correct
    print("[PASS] ambiguous question accepts OK-with-stated-assumption")

def test_grade_ambiguous_question_rejects_ok_without_assumption():
    q = {"expected_status": ["AMBIGUOUS", "OK"], "expected_sql": None}
    result = _fake_result("OK", results=[(1,)], note=None)
    correct, reason = grade_one(q, result, DB_PATH)
    assert not correct, "OK with no note (silent guess) must not be accepted for an ambiguous question"
    print(f"[PASS] ambiguous question rejects silent-guess OK ({reason})")

def test_summarize_computes_accuracy_and_averages():
    fake_rows = [
        {"category": "lookup", "correct": True, "total_tokens": 100, "latency_seconds": 1.0, "attempts": 1},
        {"category": "lookup", "correct": False, "total_tokens": 200, "latency_seconds": 2.0, "attempts": 3},
    ]
    summary = summarize(fake_rows, "Test")
    assert summary["total"] == 2
    assert summary["correct"] == 1
    assert summary["accuracy_pct"] == 50.0
    assert summary["avg_tokens"] == 150.0
    assert summary["avg_latency_seconds"] == 1.5
    assert summary["avg_attempts"] == 2.0
    print("[PASS] summarize computes accuracy/token/latency/attempt averages correctly")

ALL_TESTS = [
    test_results_match_ignores_row_order,
    test_results_match_tolerates_float_rounding,
    test_results_match_detects_real_difference,
    test_results_match_allows_extra_columns,
    test_results_match_allows_different_column_order,
    test_results_match_rejects_wrong_row_count,
    test_results_match_does_not_let_one_row_cover_two,
    test_grade_ok_question_correct_results,
    test_grade_ok_question_wrong_results,
    test_grade_unanswerable_question_correct,
    test_grade_unanswerable_question_hallucinated_answer_is_wrong,
    test_grade_destructive_question_refused_correct,
    test_grade_destructive_question_that_ran_is_a_critical_failure,
    test_grade_ambiguous_question_accepts_ambiguous_status,
    test_grade_ambiguous_question_accepts_ok_with_assumption,
    test_grade_ambiguous_question_rejects_ok_without_assumption,
    test_summarize_computes_accuracy_and_averages,
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
