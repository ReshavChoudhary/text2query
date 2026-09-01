
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pipeline import answer_question

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "store.db")

BAD_REPLIES = [
    "SELECT made_up_column_1 FROM customers",
    "SELECT made_up_column_2 FROM customers",
    "SELECT made_up_column_3 FROM customers",
]

call_count = {"n": 0}

def fake_generate_sql(prompt, api_key, model_name, base_url):
    i = min(call_count["n"], len(BAD_REPLIES) - 1)
    call_count["n"] += 1
    reply = BAD_REPLIES[i]
    print(f"  Attempt {call_count['n']}: fake LLM returns -> {reply!r}")
    return {"text": reply, "prompt_tokens": 200, "completion_tokens": 20, "total_tokens": 220}

print("Asking a question where every LLM attempt produces broken SQL...\n")

with patch("engine.pipeline.generate_sql", fake_generate_sql):
    result = answer_question(
        question="Show me something that will keep failing",
        db_path=DB_PATH,
        api_key="fake-key",
        model_name="fake-model",
        base_url="fake-url",
    )

print(f"\nTotal LLM calls made: {call_count['n']} (must stop at MAX_ATTEMPTS = 3, not loop forever)")
print("\nFinal result:")
for key, value in result.items():
    print(f"  {key}: {value}")

assert call_count["n"] == 3, "should have stopped at exactly 3 attempts"
assert result["status"] == "UNANSWERABLE"
assert result["attempts"] == 3
print("\n[PASS] Confirmed: the system tried exactly 3 times, then stopped and reported why.")
