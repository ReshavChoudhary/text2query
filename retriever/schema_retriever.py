
import sqlite3

TABLE_NOTES = {
    "customer_archive": (
        "NOTE: this holds FORMER/churned customers only (cust_id 9001+), "
        "completely separate from the 'customers' table, with zero invoices. "
        "For any question about current customers, use 'customers', not this table."
    ),
    "sales_summary": (
        "NOTE: this is a stale, pre-computed cache -- frozen at one past date and "
        "missing many customers. Do NOT use it for totals or spend/revenue questions. "
        "Compute totals from 'invoices' (or 'invoice_lines') directly instead."
    ),
}

COLUMN_NOTES = {
    ("customers", "ctry_cd"): "full country name (e.g. 'Sweden'), NOT an ISO code",
    ("invoices", "ctry_cd"): "full country name (e.g. 'Sweden'), NOT an ISO code",
    ("customer_archive", "ctry_cd"): "full country name, NOT an ISO code",
    ("invoices", "inv_date"): "format YYYY-MM-DD",
    ("customers", "signup_dt"): "format YYYY-MM-DD",
    ("customer_archive", "signup_dt"): "format YYYY-MM-DD",
    ("customer_archive", "churn_dt"): "format YYYY-MM-DD",
    ("employees", "hire_date"): "format YYYY-MM-DD",
    ("support_tickets", "opened_dt"): "format DD-MM-YYYY -- DIFFERENT from the invoices/customers date format",
    ("support_tickets", "resolved_dt"): "format DD-MM-YYYY, same as opened_dt; NULL if the ticket is still open",
}

def get_table_names(db_path):
    conn = _connect_read_only(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not tables:
        raise ValueError("The database has no tables.")

    return tables

def get_table_info(db_path, table_name):
    conn = _connect_read_only(db_path)
    cursor = conn.cursor()

    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [(row[1], row[2], bool(row[5])) for row in cursor.fetchall()]

    cursor.execute(f"PRAGMA foreign_key_list({table_name})")
    foreign_keys = [(row[3], row[2], row[4]) for row in cursor.fetchall()]

    conn.close()
    return {"columns": columns, "foreign_keys": foreign_keys}

def format_table_schema(table_name, table_info):
    lines = [f"Table: {table_name}"]
    if table_name in TABLE_NOTES:
        lines.append(f"  {TABLE_NOTES[table_name]}")

    for col_name, col_type, is_pk in table_info["columns"]:
        marker = " (PRIMARY KEY)" if is_pk else ""
        note = COLUMN_NOTES.get((table_name, col_name))
        note_text = f" -- {note}" if note else ""
        lines.append(f"  - {col_name} ({col_type}){marker}{note_text}")

    for from_col, ref_table, ref_col in table_info["foreign_keys"]:
        lines.append(f"  - {from_col} -> references {ref_table}.{ref_col}")

    return "\n".join(lines)

def read_schema(db_path, table_names=None):
    all_tables = get_table_names(db_path)

    if table_names is None:
        tables_to_describe = all_tables
    else:
        tables_to_describe = [t for t in table_names if t in all_tables]
        if not tables_to_describe:
            tables_to_describe = all_tables

    blocks = []
    for table_name in tables_to_describe:
        info = get_table_info(db_path, table_name)
        blocks.append(format_table_schema(table_name, info))

    return "\n\n".join(blocks)

def _connect_read_only(db_path):
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError as err:
        raise ConnectionError(f"Cannot open database: {err}")
