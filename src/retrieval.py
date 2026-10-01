"""Find the regulation chunks that are relevant for a chatbot question."""

from __future__ import annotations

import os

import lancedb
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from .indexing import LANCE_DB_URI, PDFS, TABLE_NAME, get_embeddings


KNOWN_BUNDESLAENDER = {pdf["bundesland"] for pdf in PDFS}

# Table columns that become Document.metadata (see build_index()).
METADATA_COLUMNS = ["bundesland", "document", "page", "page_end", "paragraph"]

QUERY_REWRITE_PROMPT = """
Rewrite the user's question as a clear German query for semantic retrieval
from German fishing regulations.

Preserve the full meaning, relationships and conditions of the original
question. Do not reduce the query to keywords.

Use terminology that is likely to occur in German legal documents where
appropriate.

The result should usually be one complete German sentence.

Return only the rewritten query.

Examples:

User:
"How big does a pike have to be?"
Query:
"Welches Mindestmaß gilt für Hechte?"

User:
"When can I catch zander?"
Query:
"Welche Schonzeit gilt für Zander?"

Keep important information such as:
- fish species
- German federal state
- regulation topic
- dates or other relevant restrictions

Return ONLY the search query.
""".strip()


def get_table() -> lancedb.table.Table:
    """Open the table created by indexing.py."""
    db = lancedb.connect(str(LANCE_DB_URI))

    if TABLE_NAME not in db.table_names():
        raise FileNotFoundError(
            f"No regulation index '{TABLE_NAME}' found in {LANCE_DB_URI}. "
            "Run `python -m src.indexing` once before starting the chatbot."
        )

    return db.open_table(TABLE_NAME)


def _row_to_document(row: dict) -> Document:
    return Document(
        page_content=row["text"],
        metadata={column: row[column] for column in METADATA_COLUMNS},
    )


def _find_bundesland_in_query(query: str) -> str | None:
    query_lower = query.lower()

    for bundesland in KNOWN_BUNDESLAENDER:
        if bundesland.lower() in query_lower:
            return bundesland

    return None


def rewrite_query_in_german(question: str) -> str:
    """The laws are German, so German queries match them much better."""
    model = ChatOpenAI(
        model="openai/gpt-5-mini",
        temperature=0,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    response = model.invoke(
        [
            {"role": "system", "content": QUERY_REWRITE_PROMPT},
            {"role": "user", "content": question},
        ]
    )

    return str(response.content).strip()


def retrieve_documents(
    question: str,
    *,
    max_chunks: int = 4,
) -> list[Document]:
    """Return the regulation chunks that best match the question."""
    question = question.strip()

    if not question:
        return []

    search_query = rewrite_query_in_german(question)

    print(f"Original query:  {question}")
    print(f"Retrieval query: {search_query}")

    bundesland = _find_bundesland_in_query(
        f"{question} {search_query}"
    )

    query_vector = get_embeddings().embed_query(search_query)

    search = (
        get_table()
        .search(
            query_type="hybrid",
            vector_column_name="vector",
        )
        .vector(query_vector)
        .text(search_query)
    )

    if bundesland is not None:
        search = search.where(
            f"bundesland = '{bundesland}'",
            prefilter=True,
        )

    rows = search.limit(max_chunks).to_list()

    return [_row_to_document(row) for row in rows]