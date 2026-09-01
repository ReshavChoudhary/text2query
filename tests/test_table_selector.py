
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retriever.table_selector import select_relevant_tables

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "store.db")

CASES = [
    ("Which 5 customers spent the most in 2024?", ["customers", "invoices"]),
    ("What is the most popular genre by number of tracks sold?", ["genres", "tracks", "invoice_lines"]),
    ("List all tracks on the Rainy Sunday playlist", ["tracks", "playlists", "playlist_track"]),
    ("Which employee has the most customers assigned to them?", ["employees", "customers"]),
    ("How many support tickets are still open?", ["support_tickets"]),
    ("What albums did the artist Autumn Anchor release?", ["albums", "artists"]),
    ("What is the average satisfaction score for resolved tickets?", ["support_tickets"]),
]

def run_tests():
    failures = []

    for question, required_tables in CASES:
        selected = select_relevant_tables(question, DB_PATH)
        missing = [t for t in required_tables if t not in selected]

        if missing:
            failures.append((question, missing, selected))
            print(f"[FAIL] {question!r} -- missing required tables: {missing} (got {selected})")
        else:
            print(f"[PASS] {question!r} -- selected {selected}")

    from retriever.schema_retriever import get_table_names
    gibberish_result = select_relevant_tables("zzz qux flerbnorp", DB_PATH)
    if set(gibberish_result) != set(get_table_names(DB_PATH)):
        failures.append(("fallback case", "expected all tables", gibberish_result))
        print(f"[FAIL] gibberish question did not fall back to all tables: {gibberish_result}")
    else:
        print("[PASS] gibberish question falls back to the full table list")

    print()
    total = len(CASES) + 1
    print(f"{total - len(failures)}/{total} passed.")
    return len(failures) == 0

if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
