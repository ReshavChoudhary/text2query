
def parse_llm_reply(raw_reply):
    if not raw_reply or not raw_reply.strip():
        return {"kind": "sql", "sql": "", "assumption": None}

    text = _extract_from_fence(raw_reply)
    if not text.strip():
        text = raw_reply
    stripped = text.strip()

    upper = stripped.upper()
    if upper.startswith("UNANSWERABLE"):
        reason = _text_after_prefix(stripped)
        return {
            "kind": "unanswerable",
            "reason": reason or "The schema does not contain this information.",
        }

    if upper.startswith("AMBIGUOUS"):
        clarification = _text_after_prefix(stripped)
        return {
            "kind": "ambiguous",
            "clarification": clarification or "This question has more than one reasonable interpretation.",
        }

    assumption = None
    kept_lines = []
    for line in raw_reply.split("\n"):
        marker_pos = line.upper().find("-- ASSUMPTION:")
        if marker_pos != -1:
            assumption = line[marker_pos + len("-- ASSUMPTION:"):].strip()
        else:
            kept_lines.append(line)

    sql = clean_sql("\n".join(kept_lines))
    return {"kind": "sql", "sql": sql, "assumption": assumption}

def _text_after_prefix(stripped):
    colon_pos = stripped.find(":")
    if colon_pos == -1:
        return ""
    return stripped[colon_pos + 1:].strip()

def clean_sql(raw_reply):
    if not raw_reply:
        return ""

    text = raw_reply

    text = _extract_from_fence(text)

    if text == raw_reply:
        text = _drop_lines_before_sql(text)

    text = _strip_trailing_semicolons(text)

    text = text.strip()

    if not text or not any(ch.isalpha() for ch in text):
        return ""

    return text

def _extract_from_fence(text):
    fence = "```"

    open_pos = text.find(fence)
    if open_pos == -1:
        return text

    after_fence = open_pos + len(fence)
    newline_pos = text.find("\n", after_fence)
    if newline_pos == -1:
        return text
    start = newline_pos + 1

    close_pos = text.find("\n" + fence, start)
    if close_pos == -1:
        if text[start:].startswith(fence):
            return ""
        return text[start:]
    else:
        return text[start:close_pos]

def _drop_lines_before_sql(text):
    lines = text.split("\n")
    for i in range(len(lines)):
        stripped = lines[i].lstrip()
        upper = stripped.upper()
        if upper.startswith("SELECT") or upper.startswith("WITH"):
            return "\n".join(lines[i:])
    return text

def _strip_trailing_semicolons(text):
    return text.rstrip(";")
