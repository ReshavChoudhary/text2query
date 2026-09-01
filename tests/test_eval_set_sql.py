
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.query_executor import run_query

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_SET_PATH = os.path.join(BASE_DIR, "eval_set.json")
DB_PATH = os.path.join(BASE_DIR, "store.db")

def run_validation():
    with open(EVAL_SET_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)

    errors = []
    empty_warnings = []
    ok_count = 0

    for q in questions:
        statuses = q["expected_status"]
        statuses = statuses if isinstance(statuses, list) else [statuses]

        if "OK" not in statuses or not q["expected_sql"]:
            continue

        ok_count += 1
        try:
            result = run_query(q["expected_sql"], DB_PATH)
        except Exception as err:
            errors.append((q["id"], q["question"], str(err)))
            print(f"[ERROR] id={q['id']} {q['question']!r} -> {err}")
            continue

        if result["row_count"] == 0:
            empty_warnings.append((q["id"], q["question"]))
            print(f"[WARN]  id={q['id']} {q['question']!r} -> 0 rows returned")
        else:
            print(f"[OK]    id={q['id']} {q['question']!r} -> {result['row_count']} row(s)")

    print(f"\n{ok_count - len(errors)}/{ok_count} OK-category gold queries ran without error.")
    if empty_warnings:
        print(f"{len(empty_warnings)} returned zero rows (check these are genuinely empty answers):")
        for qid, question in empty_warnings:
            print(f"  - id={qid}: {question}")

    total = len(questions)
    print(f"\nTotal questions in eval_set.json: {total}")
    return len(errors) == 0

if __name__ == "__main__":
    ok = run_validation()
    sys.exit(0 if ok else 1)
