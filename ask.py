
import argparse
import json
import os

from config.settings import load_config
from engine.pipeline import answer_question
from retriever.schema_retriever import get_table_names

def print_result(sql, results, status, note):
    print(json.dumps({"sql": sql, "results": results, "status": status, "note": note}))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--approach", choices=["full", "selected"], default="full")
    args = parser.parse_args()

    if not os.path.isfile(args.db):
        print_result(None, [], "UNANSWERABLE", f"Database file not found: {args.db}")
        return

    try:
        get_table_names(args.db)
    except Exception as err:
        print_result(None, [], "UNANSWERABLE", f"Could not open database: {err}")
        return

    question = args.question.strip()
    if not question:
        print_result(None, [], "UNANSWERABLE", "No question was provided.")
        return

    try:
        config = load_config()
    except ValueError as err:
        print_result(None, [], "UNANSWERABLE", str(err))
        return

    try:
        result = answer_question(
            question=question,
            db_path=args.db,
            api_key=config["api_key"],
            model_name=config["model_name"],
            base_url=config["base_url"],
            approach=args.approach,
        )
    except Exception as err:
        print_result(None, [], "UNANSWERABLE", f"Unexpected error: {err}")
        return

    print_result(result["sql"], result["results"], result["status"], result["note"])

if __name__ == "__main__":
    main()
