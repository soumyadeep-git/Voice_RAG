SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search the user's uploaded documents for passages relevant to a query. "
        "Returns numbered passages with their source document. Call multiple times with "
        "different queries when the question has several parts.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A focused search query in plain keywords.",
                }
            },
            "required": ["query"],
        },
    },
}

LIST_DOCUMENTS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_documents",
        "description": "List the documents currently in the knowledge base (filenames and how "
        "many passages each was split into). Use this for preliminary questions about which "
        "documents or files exist, or what topics are available to ask about \u2014 NOT for "
        "questions about the contents inside the documents (use search_documents for those).",
        "parameters": {"type": "object", "properties": {}},
    },
}


def format_document_list(documents: list[dict]) -> str:
    ready = [d for d in documents if d.get("status") == "ready"]
    docs = ready or documents
    if not docs:
        return "No documents have been uploaded yet."
    lines = [
        f"- {d.get('filename') or d.get('id')} ({d.get('num_chunks') or 0} passages)"
        for d in docs
    ]
    return "Documents in the knowledge base:\n" + "\n".join(lines)


def format_location(passage: dict) -> str:
    parts = []
    if passage.get("page") is not None:
        parts.append(f"p.{passage['page']}")
    if passage.get("section"):
        parts.append(passage["section"])
    return f", {' / '.join(parts)}" if parts else ""


class CitationRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, dict] = {}
        self._order: list[str] = []

    def render(self, passages: list[dict]) -> str:
        lines: list[str] = []
        for passage in passages:
            cid = passage["id"]
            if cid not in self._by_id:
                self._by_id[cid] = {"n": len(self._order) + 1, "passage": passage}
                self._order.append(cid)
            entry = self._by_id[cid]
            location = format_location(passage)
            lines.append(f"[{entry['n']}] ({passage['filename']}{location})\n{passage['text']}")
        return "\n\n".join(lines) if lines else "No matching passages found."

    def all(self) -> list[dict]:
        return [
            {"n": self._by_id[cid]["n"], **self._by_id[cid]["passage"]} for cid in self._order
        ]
