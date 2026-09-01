
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chain.output_parser import parse_llm_reply

CASES = [
    (
        "plain SQL, no assumption",
        "SELECT * FROM customers LIMIT 5",
        {"kind": "sql", "sql": "SELECT * FROM customers LIMIT 5", "assumption": None},
    ),
    (
        "SQL wrapped in a markdown fence",
        "```sql\nSELECT * FROM tracks LIMIT 3\n```",
        {"kind": "sql", "sql": "SELECT * FROM tracks LIMIT 3", "assumption": None},
    ),
    (
        "SQL with an assumption comment",
        '-- ASSUMPTION: "top selling" means by revenue\nSELECT cust_id FROM invoices',
        {"kind": "sql", "sql": "SELECT cust_id FROM invoices", "assumption": '"top selling" means by revenue'},
    ),
    (
        "UNANSWERABLE reply",
        "UNANSWERABLE: employee salary is not stored in this database",
        {"kind": "unanswerable", "reason": "employee salary is not stored in this database"},
    ),
    (
        "AMBIGUOUS reply",
        "AMBIGUOUS: do you mean total revenue or number of orders?",
        {"kind": "ambiguous", "clarification": "do you mean total revenue or number of orders?"},
    ),
    (
        "lowercase unanswerable still recognized",
        "unanswerable: no phone numbers exist",
        {"kind": "unanswerable", "reason": "no phone numbers exist"},
    ),
]

def run_tests():
    failures = []
    for label, raw_reply, expected in CASES:
        result = parse_llm_reply(raw_reply)
        if result == expected:
            print(f"[PASS] {label}")
        else:
            print(f"[FAIL] {label}\n   expected: {expected}\n   got:      {result}")
            failures.append(label)

    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} passed.")
    return len(failures) == 0

if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
