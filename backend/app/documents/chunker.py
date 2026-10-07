"""
Text chunker — splits extracted document text into overlapping chunks
while preserving page/section metadata for accurate citations.
"""
from typing import Any, Dict, List, Optional
from app.config import settings
import re
import structlog

logger = structlog.get_logger()


class DocumentChunker:
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_extracted(
        self,
        extracted: Dict[str, Any],
        document_id: str,
        filename: str,
        file_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Chunk an extracted document.
        Returns list of chunk dicts with full metadata.
        """
        pages = extracted.get("pages", [])

        if pages:
            # PDF: chunk per-page, preserving page numbers
            return self._chunk_with_pages(pages, document_id, filename, file_type)
        else:
            # DOCX/TXT/CSV/JSON: chunk the full text
            return self._chunk_flat_text(
                extracted["text"],
                document_id,
                filename,
                file_type,
                extracted.get("sections", []),
            )

    def _chunk_with_pages(
        self,
        pages: List[Dict],
        document_id: str,
        filename: str,
        file_type: str,
    ) -> List[Dict[str, Any]]:
        chunks = []
        chunk_index = 0
        for page_info in pages:
            page_num = page_info["page"]
            page_text = page_info["text"]
            sub_chunks = self._split_text(page_text)
            for sub in sub_chunks:
                if sub.strip():
                    chunks.append({
                        "chunk_index": chunk_index,
                        "content": sub.strip(),
                        "page_number": page_num,
                        "section": None,
                        "document_id": document_id,
                        "filename": filename,
                        "file_type": file_type,
                    })
                    chunk_index += 1
        return chunks

    def _chunk_flat_text(
        self,
        text: str,
        document_id: str,
        filename: str,
        file_type: str,
        sections: List[Dict],
    ) -> List[Dict[str, Any]]:
        chunks = []
        raw_chunks = self._split_text(text)
        for idx, chunk_text in enumerate(raw_chunks):
            if chunk_text.strip():
                # Try to infer section from content
                section = self._infer_section(chunk_text, sections)
                chunks.append({
                    "chunk_index": idx,
                    "content": chunk_text.strip(),
                    "page_number": None,
                    "section": section,
                    "document_id": document_id,
                    "filename": filename,
                    "file_type": file_type,
                })
        return chunks

    def _split_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap using sentence boundaries."""
        if len(text) <= self.chunk_size:
            return [text]

        # Split on paragraph or sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+|\n\n", text)
        chunks = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= self.chunk_size:
                current = (current + " " + sentence).strip()
            else:
                if current:
                    chunks.append(current)
                # Overlap: carry last N chars
                overlap_start = max(0, len(current) - self.chunk_overlap)
                current = current[overlap_start:] + " " + sentence
                current = current.strip()

        if current:
            chunks.append(current)

        return chunks

    def _infer_section(self, text: str, sections: List[Dict]) -> Optional[str]:
        """Try to match chunk content to a section heading."""
        if not sections:
            return None
        for s in sections:
            if s.get("section") and s["section"] in text[:200]:
                return s["section"]
        return None
