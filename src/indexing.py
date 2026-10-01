"""Build the vector store from the fishing-regulation PDFs.

Run this once, and again whenever the PDFs change:
    python -m src.indexing
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import lancedb
import pymupdf
from lancedb.index import FTS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
LANCE_DB_URI = DATA_DIR / "lance_db"
TABLE_NAME = "fishing_regulations"

TESSDATA_PATH = "C:/Program Files/Tesseract-OCR/tessdata"

PDFS = [
    {
        "path": RAW_DATA_DIR / "Landesverordnung_Brandenburg.pdf",
        "bundesland": "Brandenburg",
        "document": "Landesverordnung_Brandenburg",
    },
    {
        "path": RAW_DATA_DIR / "Landesverordnung_RheinlandPfalz.pdf",
        "bundesland": "Rheinland-Pfalz",
        "document": "Landesverordnung_RheinlandPfalz",
    },
    {
        "path": RAW_DATA_DIR / "Landesverordnung_Bayern.pdf",
        "bundesland": "Bayern",
        "document": "Landesverordnung_Bayern",
    },
    {
        "path": RAW_DATA_DIR / "Landesverordnung_Berlin.pdf",
        "bundesland": "Berlin",
        "document": "Landesverordnung_Berlin",
    },
    {
        "path": RAW_DATA_DIR / "Landesverordnung_BadenWürttemberg.pdf",
        "bundesland": "Baden-Württemberg",
        "document": "Landesverordnung_BadenWürttemberg",
    },
]

# A line that starts a new legal paragraph, e.g. "§ 17" or "§ 3a".
PARAGRAPH_PATTERN = r"§\s*(\d{1,3}[a-zA-Z]?)"


def get_embeddings() -> OpenAIEmbeddings:
    """Indexing and retrieval must use the same embedding model."""
    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )


def load_documents() -> list[Document]:
    """OCR the PDFs and return one Document per page that contains text."""
    documents: list[Document] = []

    for pdf_info in PDFS:
        pdf_path = pdf_info["path"]
        bundesland = pdf_info["bundesland"]
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
                                "bundesland": bundesland,
                                "document": document_name,
                                "page": page_number + 1,
                            },
                        )
                    )

                print(
                    f"{bundesland} - Page {page_number + 1}: "
                    f"{len(text)} characters"
                )
        finally:
            pdf.close()

    return documents


def _normalize_paragraph_marker(line: str) -> str:
    """Fix paragraph markers that OCR misread.

    Examples:
        §17 -> § 17
        817 -> § 17
        $17 -> § 17
    """
    stripped = line.strip()

    # Correctly recognized paragraph marker.
    match = re.fullmatch(PARAGRAPH_PATTERN, stripped)

    if match:
        return f"§ {match.group(1)}"

    # Common OCR errors where § is recognized as 8 or $.
    match = re.fullmatch(r"[8$](\d{1,3}[a-zA-Z]?)", stripped)

    if match:
        return f"§ {match.group(1)}"

    return line


def split_legal_documents(documents: list[Document]) -> list[Document]:
    """Split the laws into one chunk per legal paragraph (§).

    Pages of the same law are processed continuously, so a paragraph that
    spans a page break stays in one chunk.
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
                "bundesland": first_page.metadata.get("bundesland"),
                "document": document_name,
                "page": page_start,
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

                paragraph_match = re.fullmatch(PARAGRAPH_PATTERN, line.strip())

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


def build_index() -> lancedb.table.Table:
    """OCR the PDFs, split them by legal paragraph and rebuild LanceDB."""
    documents = load_documents()

    print(f"\nLoaded {len(documents)} pages with text")

    chunks = split_legal_documents(documents)

    print(f"Created {len(chunks)} legal chunks")

    vectors = get_embeddings().embed_documents(
        [chunk.page_content for chunk in chunks]
    )

    # One explicit column per field, so LanceDB can filter on them.
    rows = [
        {
            "id": f"{chunk.metadata['document']}_{index}",
            "vector": vector,
            "text": chunk.page_content,
            "bundesland": chunk.metadata["bundesland"],
            "document": chunk.metadata["document"],
            "page": chunk.metadata["page"],
            "page_end": chunk.metadata["page_end"],
            "paragraph": chunk.metadata["paragraph"],
        }
        for index, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    # Rebuilding should not append a second copy of every chunk.
    db = lancedb.connect(str(LANCE_DB_URI))
    table = db.create_table(TABLE_NAME, data=rows, mode="overwrite")

    # Full-text index on the chunk text for later keyword search.
    table.create_index("text", config=FTS(language="German"), replace=True)

    print(f"Stored chunks in {LANCE_DB_URI} / {TABLE_NAME}")

    return table


if __name__ == "__main__":
    build_index()
