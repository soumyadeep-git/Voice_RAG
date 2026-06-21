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
