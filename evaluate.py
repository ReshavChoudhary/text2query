
import argparse
import json
import time
from collections import defaultdict

from config.settings import load_config
from engine.pipeline import answer_question
from executor.query_executor import run_query

def normalize_value(value):
    if isinstance(value, float):
        return round(value, 2)
    return value

def normalize_row(row):
    return tuple(normalize_value(v) for v in row)

def results_match(expected_rows, actual_rows):
    if len(expected_rows) != len(actual_rows):
        return False

    expected_sets = [frozenset(normalize_row(r)) for r in expected_rows]
    actual_sets = [frozenset(normalize_row(r)) for r in actual_rows]

    used = [False] * len(actual_sets)
    for expected in expected_sets:
        found_match = False
        for i, actual in enumerate(actual_sets):
            if not used[i] and expected.issubset(actual):
                used[i] = True
                found_match = True
                break
        if not found_match:
            return False
    return True

def grade_one(question, result, db_path):
    expected_statuses = question["expected_status"]
    expected_statuses = expected_statuses if isinstance(expected_statuses, list) else [expected_statuses]
    actual_status = result["status"]

    if actual_status not in expected_statuses:
        return False, f"expected status in {expected_statuses}, got {actual_status}"

    if "AMBIGUOUS" in expected_statuses and actual_status == "OK":
        if not result["note"]:
            return False, "status OK but no assumption was stated in note (required for an ambiguous question)"
        return True, "OK with assumption stated"

    if actual_status != "OK":
        return True, "status matched"

    if not question.get("expected_sql"):
        return True, "status matched (no gold SQL to check against)"

    try:
        gold = run_query(question["expected_sql"], db_path)
    except Exception as err:
        return False, f"gold SQL itself failed to run: {err}"

    if results_match(gold["rows"], result["results"]):
        return True, "results matched the gold query"
    return False, f"results did not match gold query (expected {gold['row_count']} row(s), got {len(result['results'])})"

def run_evaluation(questions, db_path, config, approach):
    per_question = []
    for q in questions:
        result = answer_question(
            question=q["question"],
            db_path=db_path,
            api_key=config["api_key"],
            model_name=config["model_name"],
            base_url=config["base_url"],
            approach=approach,
        )
        is_correct, reason = grade_one(q, result, db_path)
        per_question.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "expected_status": q["expected_status"],
            "actual_status": result["status"],
            "sql": result["sql"],
            "results": result["results"],
            "note": result["note"],
            "attempts": result["attempts"],
            "total_tokens": result["total_tokens"],
            "latency_seconds": result["latency_seconds"],
            "correct": is_correct,
            "grading_reason": reason,
        })
        mark = "PASS" if is_correct else "FAIL"
        print(f"[{approach:8s}] [{mark}] id={q['id']:>2} ({q['category']:<12}) {q['question'][:55]}")
    return per_question

def summarize(per_question, approach_name):
    total = len(per_question)
    correct = sum(1 for r in per_question if r["correct"])
    accuracy = round(100 * correct / total, 1) if total else 0.0

    tokens = [r["total_tokens"] for r in per_question if r["total_tokens"]]
    avg_tokens = round(sum(tokens) / len(tokens), 1) if tokens else None

    latencies = [r["latency_seconds"] for r in per_question]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    attempts = [r["attempts"] for r in per_question]
    avg_attempts = round(sum(attempts) / len(attempts), 2) if attempts else 0.0

    by_category = defaultdict(lambda: [0, 0])
    for r in per_question:
        by_category[r["category"]][1] += 1
        if r["correct"]:
            by_category[r["category"]][0] += 1

    print(f"\n=== {approach_name} summary ===")
    print(f"Total questions: {total}")
    print(f"Correct: {correct}")
    print(f"Execution accuracy: {accuracy}%")
    print(f"Average tokens per question: {avg_tokens}")
    print(f"Average latency per question: {avg_latency}s")
    print(f"Average attempts per question: {avg_attempts}")
    print("Accuracy by category:")
    for cat, (c, t) in sorted(by_category.items()):
        print(f"  {cat}: {c}/{t} ({round(100 * c / t, 1)}%)")

    return {
        "approach": approach_name,
        "total": total,
        "correct": correct,
        "accuracy_pct": accuracy,
        "avg_tokens": avg_tokens,
        "avg_latency_seconds": avg_latency,
        "avg_attempts": avg_attempts,
        "by_category": {cat: {"correct": c, "total": t} for cat, (c, t) in by_category.items()},
    }

def main():
    parser = argparse.ArgumentParser(description="Evaluate the text-to-SQL system on eval_set.json")
    parser.add_argument("--db", default="store.db")
    parser.add_argument("--eval-set", default="eval_set.json")
    parser.add_argument("--out", default="eval_results.json", help="Where to save detailed results")
    args = parser.parse_args()

    config = load_config()

    with open(args.eval_set, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Loaded {len(questions)} questions from {args.eval_set}\n")

    print("=" * 70)
    print("Running Approach A -- full schema in every prompt")
    print("=" * 70)
    start_a = time.time()
    results_a = run_evaluation(questions, args.db, config, "full")
    time_a = time.time() - start_a

    print()
    print("=" * 70)
    print("Running Approach B -- only relevant tables selected per question")
    print("=" * 70)
    start_b = time.time()
    results_b = run_evaluation(questions, args.db, config, "selected")
    time_b = time.time() - start_b

    summary_a = summarize(results_a, "Approach A (full schema)")
    summary_b = summarize(results_b, "Approach B (selected tables)")

    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)
    print(f"{'Approach':<28} {'Accuracy':>10} {'Avg Tokens':>12} {'Avg Latency':>13}")
    print(f"{'A (full schema)':<28} {summary_a['accuracy_pct']:>9}% "
          f"{str(summary_a['avg_tokens']):>12} {summary_a['avg_latency_seconds']:>12}s")
    print(f"{'B (selected tables)':<28} {summary_b['accuracy_pct']:>9}% "
          f"{str(summary_b['avg_tokens']):>12} {summary_b['avg_latency_seconds']:>12}s")

    out = {
        "approach_a": {"summary": summary_a, "questions": results_a, "total_wall_time_seconds": round(time_a, 1)},
        "approach_b": {"summary": summary_b, "questions": results_b, "total_wall_time_seconds": round(time_b, 1)},
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nDetailed results saved to {args.out}")

if __name__ == "__main__":
    main()
