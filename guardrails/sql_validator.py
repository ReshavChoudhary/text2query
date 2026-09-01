
import re

def check_safety(sql):
    if not sql or not sql.strip():
        return False, "The statement is empty."

    stripped = _strip_comments(sql)

    if not stripped or not stripped.strip():
        return False, "The statement contains only comments or whitespace."

    first_word = _get_first_word(stripped)
    if not first_word:
        return False, "Could not find a SQL keyword in the statement."

    first_word_upper = first_word.upper()

    if first_word_upper not in ("SELECT", "WITH"):
        return False, f"Blocked: statements starting with {first_word_upper} are not allowed."

    if _has_multiple_statements(sql):
        return False, "Blocked: multiple statements are not allowed."

    if first_word_upper == "WITH":
        if _with_body_is_write(stripped):
            return False, "Blocked: WITH clause followed by a write operation."

    return True, ""

def _strip_comments(sql):
    text = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    text = re.sub(r"--[^\n]*", " ", text)
    return text

def _get_first_word(text):
    text = text.strip()
    match = re.match(r"[A-Za-z]+", text)
    if match:
        return match.group(0)
    return ""

def _has_multiple_statements(sql):
    in_single_quote = False
    in_double_quote = False

    for i in range(len(sql)):
        ch = sql[i]

        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif ch == ";" and not in_single_quote and not in_double_quote:
            rest = sql[i + 1:].strip()
            if rest and any(c.isalpha() for c in rest):
                return True

    return False

def _with_body_is_write(stripped):
    upper = stripped.upper()
    write_keywords = ("INSERT", "UPDATE", "DELETE", "REPLACE")

    depth = 0
    found_as = False
    i = 0

    while i < len(upper):
        if upper[i].isspace():
            i += 1
            continue

        if upper[i] == "(":
            depth += 1
            i += 1
            continue
        if upper[i] == ")":
            depth -= 1
            i += 1
            if depth == 0 and found_as:
                rest = upper[i:].strip()
                if rest.startswith(","):
                    found_as = False
                    i += 1
                    continue
                for keyword in write_keywords:
                    if rest.startswith(keyword):
                        return True
                return False
            continue

        if depth == 0:
            word_match = re.match(r"[A-Za-z_]+", upper[i:])
            if word_match:
                word = word_match.group(0)
                if word == "AS":
                    found_as = True
                i += len(word)
                continue

        i += 1

    return False
