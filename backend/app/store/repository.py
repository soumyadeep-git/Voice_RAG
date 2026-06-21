from typing import Optional

from app.store.db import get_connection, transaction


def create_document(doc_id: str, filename: str, content_type: str, size_bytes: int) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT INTO documents (id, filename, content_type, size_bytes, status) "
            "VALUES (?, ?, ?, ?, 'pending')",
            (doc_id, filename, content_type, size_bytes),
        )


def set_document_status(doc_id: str, status: str, error: Optional[str] = None) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE documents SET status = ?, error = ? WHERE id = ?",
            (status, error, doc_id),
        )


def set_document_chunks(doc_id: str, num_chunks: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE documents SET num_chunks = ?, status = 'ready' WHERE id = ?",
            (num_chunks, doc_id),
        )


def insert_chunks(rows: list[dict]) -> None:
    with transaction() as conn:
        conn.executemany(
            "INSERT INTO chunks (id, document_id, ordinal, text, page, section, char_start, char_end) "
            "VALUES (:id, :document_id, :ordinal, :text, :page, :section, :char_start, :char_end)",
            rows,
        )


def list_documents() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, filename, content_type, size_bytes, num_chunks, status, error, created_at "
        "FROM documents ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_document(doc_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def get_all_chunks() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT c.id, c.document_id, c.ordinal, c.text, c.page, c.section, "
        "d.filename FROM chunks c JOIN documents d ON c.document_id = d.id"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_document(doc_id: str) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


def create_conversation(conv_id: str) -> None:
    with transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO conversations (id) VALUES (?)", (conv_id,))


def get_conversation(conv_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    return dict(row) if row else None


def list_conversations() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT c.id, c.created_at, c.summary, "
        "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count "
        "FROM conversations c ORDER BY c.created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def add_message(
    msg_id: str, conv_id: str, role: str, content: str, citations: Optional[str] = None
) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, citations) "
            "VALUES (?, ?, ?, ?, ?)",
            (msg_id, conv_id, role, content, citations),
        )


def get_messages(conv_id: str, limit: Optional[int] = None, offset: int = 0) -> list[dict]:
    conn = get_connection()
    sql = (
        "SELECT id, role, content, citations, created_at FROM messages "
        "WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC"
    )
    params: tuple = (conv_id,)
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params = (conv_id, limit, offset)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_ready_documents() -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE status = 'ready'"
    ).fetchone()
    return int(row["n"]) if row else 0


def count_messages(conv_id: str) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?", (conv_id,)
    ).fetchone()
    return int(row["n"]) if row else 0


def update_summary(conv_id: str, summary: str, summary_count: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE conversations SET summary = ?, summary_count = ? WHERE id = ?",
            (summary, summary_count, conv_id),
        )
