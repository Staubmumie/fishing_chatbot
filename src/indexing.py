"""Create and query the fishing-regulation vector store.

Run this file directly when the legal PDFs change to rebuild the index:
    python indexing.py

Importing this module does NOT OCR/re-index the PDFs. The chatbot can safely
import ``retrieve_documents`` at runtime.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import lancedb
import pymupdf
from langchain_core.documents import Document
from langchain_lancedb import LanceDB
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
LANCE_DB_URI = DATA_DIR / "lance_db"
TABLE_NAME = "brandenburg_fishing_regulations"

TESSDATA_PATH = "C:/Program Files/Tesseract-OCR/tessdata"

PDFS = [
    {
        "path": RAW_DATA_DIR / "Landesverordnung_Brandenburg.pdf",
        "state": "Brandenburg",
        "document": "Landesverordnung_Brandenburg",
    },
    {
        "path": RAW_DATA_DIR / "Landesverordnung_RheinlandPfalz.pdf",
        "state": "Rheinland-Pfalz",
        "document": "Landesverordnung_RheinlandPfalz",
    },
]

KNOWN_STATES = {pdf["state"] for pdf in PDFS}


def get_embeddings() -> OpenAIEmbeddings:
    """Return the same embedding model for indexing and retrieval."""
    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        check_embedding_ctx_length=False,
    )


def load_documents() -> list[Document]:
    """OCR the configured legal PDFs and return one Document per text page."""
    documents: list[Document] = []

    for pdf_info in PDFS:
        pdf_path = Path(pdf_info["path"])
        state = pdf_info["state"]
        document_name = pdf_info["document"]

        print(f"\nProcessing: {document_name}")

        pdf = pymupdf.open(pdf_path)

        try:
            for page_number, page in enumerate(pdf):
                textpage = page.get_textpage_ocr(
                    language="deu",
                    dpi=300,
                    tessdata=TESSDATA_PATH,
                )

                text = page.get_text("text", textpage=textpage)

                if text.strip():
                    documents.append(
                        Document(
                            page_content=text,
                            metadata={
                                "state": state,
                                "document": document_name,
                                "source": str(pdf_path),
                                "page": page_number + 1,
                            },
                        )
                    )

                print(
                    f"{state} - Page {page_number + 1}: "
                    f"{len(text)} characters"
                )
        finally:
            pdf.close()

    return documents


def _normalize_paragraph_marker(line: str) -> str:
    """Normalize OCR errors in paragraph markers.

    Examples:
        § 17 -> § 17
        §17  -> § 17
        817  -> § 17
        $17  -> § 17
    """
    stripped = line.strip()

    # Correctly recognized paragraph marker.
    match = re.fullmatch(r"§\s*(\d{1,3}[a-zA-Z]?)", stripped)

    if match:
        return f"§ {match.group(1)}"

    # Common OCR errors where § is recognized as 8 or $.
    match = re.fullmatch(r"[8$](\d{1,3}[a-zA-Z]?)", stripped)

    if match:
        return f"§ {match.group(1)}"

    return line


def split_legal_documents(documents: list[Document]) -> list[Document]:
    """Split legal documents by paragraph instead of character count.

    Pages belonging to the same law are processed continuously, so a paragraph
    may span multiple PDF pages without being split at the page boundary.
    """
    chunks: list[Document] = []

    # Group PDF pages by legal document.
    grouped_documents: dict[str, list[Document]] = {}

    for document in documents:
        document_name = document.metadata.get("document", "unknown")
        grouped_documents.setdefault(document_name, []).append(document)

    for document_name, pages in grouped_documents.items():
        pages.sort(key=lambda document: document.metadata.get("page", 0))

        current_lines: list[str] = []
        current_paragraph: str | None = None
        page_start: int | None = None
        page_end: int | None = None

        first_page = pages[0]

        def save_current_chunk() -> None:
            """Save the currently collected paragraph."""
            if not current_lines:
                return

            content = "\n".join(current_lines).strip()

            if not content:
                return

            metadata = {
                "state": first_page.metadata.get("state"),
                "document": document_name,
                "source": first_page.metadata.get("source"),
                "page": page_start,
                "page_start": page_start,
                "page_end": page_end,
                "paragraph": current_paragraph,
            }

            chunks.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                )
            )

        for page in pages:
            page_number = page.metadata.get("page")

            for raw_line in page.page_content.splitlines():
                line = _normalize_paragraph_marker(raw_line)

                paragraph_match = re.fullmatch(
                    r"§\s*(\d{1,3}[a-zA-Z]?)",
                    line.strip(),
                )

                # A new paragraph starts -> save the previous one.
                if paragraph_match:
                    save_current_chunk()

                    current_lines = [line]
                    current_paragraph = paragraph_match.group(1)
                    page_start = page_number
                    page_end = page_number

                    continue

                # Content before the first § is also kept.
                if not current_lines:
                    page_start = page_number

                current_lines.append(line)
                page_end = page_number

        # Save final paragraph.
        save_current_chunk()

    return chunks


def build_index() -> LanceDB:
    """OCR PDFs, split them by legal paragraph and rebuild LanceDB."""
    documents = load_documents()

    print(f"\nLoaded {len(documents)} pages with text")

    chunks = split_legal_documents(documents)

    print(f"Created {len(chunks)} legal chunks")

    embeddings = get_embeddings()

    # Rebuilding should not append a second copy of every chunk.
    db = lancedb.connect(str(LANCE_DB_URI))

    if TABLE_NAME in db.table_names():
        db.drop_table(TABLE_NAME)

    vector_store = LanceDB.from_documents(
        documents=chunks,
        embedding=embeddings,
        uri=str(LANCE_DB_URI),
        table_name=TABLE_NAME,
    )

    print(f"Stored chunks in {LANCE_DB_URI} / {TABLE_NAME}")

    return vector_store


def get_vector_store() -> LanceDB:
    """Open the already-created regulation vector store."""
    if not LANCE_DB_URI.exists():
        raise FileNotFoundError(
            f"No LanceDB index found at {LANCE_DB_URI}. "
            "Run indexing.py once before starting the chatbot."
        )

    return LanceDB(
        uri=str(LANCE_DB_URI),
        table_name=TABLE_NAME,
        embedding_function=get_embeddings(),
    )


def _state_from_query(query: str) -> str | None:
    """Very small first-pass metadata extractor for known federal states."""
    query_lower = query.lower()

    for state in KNOWN_STATES:
        if state.lower() in query_lower:
            return state

    return None

def translate_retrieval_query(query: str) -> str:
    """Convert a user question into a short German legal search query."""

    model = ChatOpenAI(
        model="openai/gpt-5-mini",
        temperature=0,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    response = model.invoke(
        [
            {
                "role": "system",
                "content": """
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
""".strip(),
            },
            {
                "role": "user",
                "content": query,
            },
        ]
    )

    return str(response.content).strip()

def retrieve_documents(
    query: str,
    *,
    k: int = 4,
) -> list[Document]:
    """Retrieve legal chunks for a chatbot question."""

    original_query = query.strip()

    if not original_query:
        return []

    # Translate/normalize only for retrieval.
    search_query = translate_retrieval_query(original_query)

    print(f"Original query:  {original_query}")
    print(f"Retrieval query: {search_query}")

    vector_store = get_vector_store()

    # Use both queries so the state can be recognized from either one.
    state = _state_from_query(
        f"{original_query} {search_query}"
    )

    candidate_count = max(k * 3, k) if state else k

    documents = vector_store.similarity_search(
        search_query,
        k=candidate_count,
    )

    if state:
        documents = [
            document
            for document in documents
            if document.metadata.get("state") == state
        ]
       

    return documents


if __name__ == "__main__":
    store = build_index()

    # test_query = "Welche Schonzeiten gelten für Lachse in Brandenburg?"

    # results = store.similarity_search(
    #     test_query,
    #     k=3,
    # )

    # print("\nRelevant chunks:")

    # for result in results:
    #     print("--------------------------------")
    #     print(result.page_content)
    #     print(result.metadata)

