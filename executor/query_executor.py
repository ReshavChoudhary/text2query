
import sqlite3
import threading

def run_query(sql, db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    timer = threading.Timer(10.0, conn.interrupt)
    timer.start()

    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchmany(1000)
        row_count = len(rows)
    except sqlite3.OperationalError as err:
        if "interrupted" in str(err).lower():
            raise TimeoutError("The query took too long (over 10 seconds).")
        raise
    finally:
        timer.cancel()
        conn.close()

    return {
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
    }
