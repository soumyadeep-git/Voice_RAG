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
