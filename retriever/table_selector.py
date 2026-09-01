
from retriever.schema_retriever import get_table_names, get_table_info, read_schema

SYNONYMS = {
    "customers": ["customer", "client", "buyer"],
    "customer_archive": ["archive", "archived", "churn", "churned", "former", "inactive"],
    "invoices": ["invoice", "purchase", "order", "spend", "spent", "revenue", "sale", "sold", "bought", "paid", "earning"],
    "invoice_lines": ["line item", "quantity"],
    "tracks": ["track", "song"],
    "albums": ["album", "record"],
    "artists": ["artist", "band", "musician"],
    "genres": ["genre", "category"],
    "media_types": ["format"],
    "playlists": ["playlist"],
    "playlist_track": ["playlist"],
    "employees": ["employee", "staff", "manager", "rep", "representative"],
    "support_tickets": ["ticket", "support", "complaint", "issue"],
    "sales_summary": ["sales summary"],
}

def select_relevant_tables(question, db_path, max_tables=6):
    all_tables = get_table_names(db_path)
    question_lower = question.lower()

    scored = [(_score_table(t, question_lower, db_path), t) for t in all_tables]
    scored = [(score, t) for score, t in scored if score > 0]

    if not scored:
        return all_tables

    scored.sort(reverse=True)
    matched = {table for _, table in scored[:max_tables]}

    expanded = set(matched)
    for table in matched:
        expanded.update(_connected_tables(table, db_path))

    return [t for t in all_tables if t in expanded]

def build_schema_for_question(question, db_path, max_tables=6):
    tables = select_relevant_tables(question, db_path, max_tables=max_tables)
    return read_schema(db_path, table_names=tables)

def _score_table(table, question_lower, db_path):
    score = 0

    for word in table.replace("_", " ").split():
        if _stem_present(word, question_lower):
            score += 1

    info = get_table_info(db_path, table)
    for col_name, _col_type, _is_pk in info["columns"]:
        for part in col_name.split("_"):
            if len(part) > 2 and _stem_present(part, question_lower):
                score += 1

    for synonym in SYNONYMS.get(table, []):
        if synonym in question_lower:
            score += 2

    return score

def _stem_present(word, question_lower):
    stem = word[:-1] if word.endswith("s") and len(word) > 3 else word
    return stem in question_lower

def _connected_tables(table, db_path):
    neighbors = set()

    info = get_table_info(db_path, table)
    for _from_col, ref_table, _ref_col in info["foreign_keys"]:
        neighbors.add(ref_table)

    for other_table in get_table_names(db_path):
        if other_table == table:
            continue
        other_info = get_table_info(db_path, other_table)
        for _from_col, ref_table, _ref_col in other_info["foreign_keys"]:
            if ref_table == table:
                neighbors.add(other_table)

    return neighbors
